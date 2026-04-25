from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.db.models import QuerySet

from memberships.models import Ownership

from ..models import BotNetResult, BrokerSyncRun, BrokerTrade, FuturesPosition, IncomeEvent
from .eur_converter import EurConverter
from .fifo_calculator import (
    GAP_REASON_BALANCE_TRANSFER_IN,
    GAP_REASON_MISSING_DATA,
    GAP_REASON_PRE_PERIOD_BUY,
    calculate_fifo_for_asset,
)


def _to_float(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01")))


def _source_label(source: str, asset: str) -> str:
    mapping: dict[str, str] = {
        "pionex_staking_api": "Pionex Earn/Rebase",
        "pionex_staking_csv": "Pionex Earn/Rebase",
        "pionex_dual_invest_api": "Pionex Dual Investment",
        "pionex_commission_csv": "Pionex CommissionIn",
        "binance_earn_api": f"Binance Earn {asset}",
        "binance_earn_csv": f"Binance Earn {asset}",
        "binance_referral_csv": "Binance Referral",
        "manual": "Manual",
    }
    return mapping.get(source, source)


def _extract_quote_asset_for_futures(symbol: str) -> str:
    if "_" in symbol:
        parts = symbol.split("_")
        if len(parts) >= 2:
            return parts[1].replace("PERP", "").strip().upper() or "USDT"
    return "USDT"


def _build_data_sources(
    *,
    trade_sources: set[str],
    income_sources: set[str],
    futures_sources: set[str],
) -> dict[str, Any]:
    pionex_api = any(source.startswith("pionex_api") for source in trade_sources) or (
        IncomeEvent.Source.PIONEX_DUAL_INVEST_API in income_sources
        or IncomeEvent.Source.PIONEX_STAKING_API in income_sources
    )
    binance_api = any(source.startswith("binance_api") for source in trade_sources) or (
        IncomeEvent.Source.BINANCE_EARN_API in income_sources
    )

    pionex_csv: set[str] = set()
    if BrokerTrade.Source.PIONEX_CSV in trade_sources:
        pionex_csv.add("trading")
    if FuturesPosition.Source.PIONEX_CSV in futures_sources:
        pionex_csv.add("futures")
    if IncomeEvent.Source.PIONEX_STAKING_CSV in income_sources:
        pionex_csv.add("staking")
    if IncomeEvent.Source.PIONEX_COMMISSION_CSV in income_sources:
        pionex_csv.add("others")

    binance_csv: set[str] = set()
    if BrokerTrade.Source.BINANCE_CSV in trade_sources:
        binance_csv.add("trades")
    if IncomeEvent.Source.BINANCE_EARN_CSV in income_sources:
        binance_csv.add("earn")
    if IncomeEvent.Source.BINANCE_REFERRAL_CSV in income_sources:
        binance_csv.add("referral")

    return {
        "pionex_api": pionex_api,
        "pionex_csv_fallback": sorted(pionex_csv),
        "binance_api": binance_api,
        "binance_csv_fallback": sorted(binance_csv),
    }


def _filter_year(queryset: QuerySet, *, field: str, year: int) -> QuerySet:
    return queryset.filter(**{f"{field}__year": year})


def _build_source_comparison(*, ownership: Ownership) -> dict[str, Any]:
    api_sources = (BrokerTrade.Source.PIONEX_API, BrokerTrade.Source.PIONEX_BOT_API)
    api_map: dict[str, dict[str, Any]] = {}
    for t in BrokerTrade.objects.filter(
        credential__ownership=ownership,
        source__in=api_sources,
    ).values("fiscal_identity_key", "quantity", "price", "timestamp"):
        key = t["fiscal_identity_key"]
        if key:
            api_map[key] = t

    csv_map: dict[str, dict[str, Any]] = {}
    for t in BrokerTrade.objects.filter(
        credential__ownership=ownership,
        source=BrokerTrade.Source.PIONEX_CSV,
    ).values("fiscal_identity_key", "quantity", "price", "timestamp"):
        key = t["fiscal_identity_key"]
        if key:
            csv_map[key] = t

    matched = api_only = csv_only = conflicting_amount = conflicting_timestamp = 0
    for key in set(api_map) | set(csv_map):
        api = api_map.get(key)
        csv = csv_map.get(key)
        if api and csv:
            matched += 1
            qty_diff = abs(Decimal(str(api["quantity"])) - Decimal(str(csv["quantity"])))
            if qty_diff > Decimal("0.0001"):
                conflicting_amount += 1
            api_ts = api["timestamp"].replace(second=0, microsecond=0)
            csv_ts = csv["timestamp"].replace(second=0, microsecond=0)
            if abs((api_ts - csv_ts).total_seconds()) > 120:
                conflicting_timestamp += 1
        elif api:
            api_only += 1
        else:
            csv_only += 1

    return {
        "matched": matched,
        "api_only": api_only,
        "csv_only": csv_only,
        "conflicting_amount": conflicting_amount,
        "conflicting_timestamp": conflicting_timestamp,
    }


def _compute_resumen_declarable(
    *,
    ganancias_perdidas_trades: list[dict[str, Any]],
    ganancias_perdidas_futuros: list[dict[str, Any]],
    total_capital: Decimal,
) -> dict[str, Any]:
    decl_ganancias = Decimal("0")
    decl_perdidas = Decimal("0")
    for section in ganancias_perdidas_trades:
        for sale in section.get("sales", []):
            if sale.get("gap_quantity", 0) > 0:
                continue
            lot_cost = sum(
                Decimal(str(lot["cost_eur"])) + Decimal(str(lot["fee_eur_allocated"]))
                for lot in sale.get("matched_lots", [])
            )
            neto_sale = Decimal(str(sale["proceeds_eur"])) - lot_cost
            if neto_sale >= 0:
                decl_ganancias += neto_sale
            else:
                decl_perdidas += abs(neto_sale)
    for future in ganancias_perdidas_futuros:
        value = Decimal(str(future["net_pnl_eur"]))
        if value >= 0:
            decl_ganancias += value
        else:
            decl_perdidas += abs(value)
    return {
        "total_capital_mobiliario_eur": _to_float(total_capital),
        "total_ganancias_eur": _to_float(decl_ganancias),
        "total_perdidas_eur": _to_float(decl_perdidas),
        "neto_ganancias_perdidas_eur": _to_float(decl_ganancias - decl_perdidas),
    }


def _build_reliability(
    *,
    ownership: Ownership,
    ganancias_perdidas_trades: list[dict[str, Any]],
    data_sources: dict[str, Any],
) -> dict[str, Any]:
    fifo_gaps: list[dict[str, Any]] = []
    for section in ganancias_perdidas_trades:
        for sale in section.get("sales", []):
            gap_qty = sale.get("gap_quantity", 0)
            gap_reason = sale.get("gap_reason")
            if gap_qty and gap_qty > 0 and gap_reason:
                fifo_gaps.append(
                    {
                        "type": "fifo_gap",
                        "asset": section["denominacion"],
                        "sell_trade_id": sale["sell_trade_id"],
                        "gap_quantity": gap_qty,
                        "gap_reason": gap_reason,
                    }
                )

    recon_gaps: list[dict[str, Any]] = []
    for run in BrokerSyncRun.objects.filter(credential__ownership=ownership).only("gaps"):
        for gap in run.gaps if isinstance(run.gaps, list) else []:
            if (
                isinstance(gap, dict)
                and gap.get("source") == "balance_reconciliation"
                and gap.get("reason") == "balance_mismatch"
            ):
                recon_gaps.append(gap)

    blocking_gaps_material = [
        g
        for g in fifo_gaps
        if g["gap_reason"] in (GAP_REASON_BALANCE_TRANSFER_IN, GAP_REASON_MISSING_DATA)
    ]
    pre_period_gaps = [g for g in fifo_gaps if g["gap_reason"] == GAP_REASON_PRE_PERIOD_BUY]

    if blocking_gaps_material:
        status = "blocked_missing_cost_basis"
        blocking_gaps_out: list[dict[str, Any]] = blocking_gaps_material
    elif recon_gaps:
        status = "blocked_unreconciled_balances"
        blocking_gaps_out = recon_gaps
    elif pre_period_gaps:
        status = "provisional"
        blocking_gaps_out = pre_period_gaps
    else:
        status = "declarable"
        blocking_gaps_out = []

    return {
        "status": status,
        "blocking_gaps": blocking_gaps_out,
        "input_coverage": data_sources,
        "source_comparison": _build_source_comparison(ownership=ownership),
    }


def generate_fiscal_report(*, ownership: Ownership, year: int) -> dict[str, Any]:
    eur_converter = EurConverter()
    avisos: list[str] = []

    income_qs = _filter_year(
        IncomeEvent.objects.filter(credential__ownership=ownership),
        field="timestamp",
        year=year,
    )
    income_grouped: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))
    for income in income_qs:
        amount_eur = eur_converter.convert_amount_to_eur(
            amount=Decimal(income.amount),
            asset=income.asset,
            trade_date=income.timestamp.date(),
        )
        income_grouped[(income.source, income.asset)] += amount_eur

    capital_mobiliario = [
        {
            "fuente": _source_label(source, asset),
            "asset": asset,
            "importe_eur": _to_float(total),
            "casilla": "029",
        }
        for (source, asset), total in sorted(income_grouped.items(), key=lambda item: item[0])
    ]

    bot_qs = _filter_year(
        BotNetResult.objects.filter(credential__ownership=ownership),
        field="period_end",
        year=year,
    )
    ganancias_perdidas_bots: list[dict[str, Any]] = []
    for bot in bot_qs:
        amount_eur = eur_converter.convert_amount_to_eur(
            amount=Decimal(bot.realized_profit),
            asset=bot.quote_asset,
            trade_date=bot.period_end.date(),
        )
        ganancias_perdidas_bots.append(
            {
                "bot_label": bot.label,
                "bot_type": bot.bot_type,
                "periodo": f"{bot.period_start.date().isoformat()}/{bot.period_end.date().isoformat()}",
                "ganancia_neta_eur": _to_float(amount_eur),
                "casilla": "332",
                "aviso_simplificacion": True,
                "incluido_en_resumen_fiscal": False,
            }
        )
    if ganancias_perdidas_bots:
        avisos.append(
            "Grid bots: la vista de bots es solo informativa y no se suma al resumen fiscal. "
            "Para declaracion, usar el detalle FIFO por operaciones."
        )

    futures_qs = _filter_year(
        FuturesPosition.objects.filter(credential__ownership=ownership),
        field="close_time",
        year=year,
    )
    ganancias_perdidas_futuros: list[dict[str, Any]] = []
    for position in futures_qs:
        quote_asset = _extract_quote_asset_for_futures(position.symbol)
        net_pnl_eur = eur_converter.convert_amount_to_eur(
            amount=Decimal(position.net_pnl),
            asset=quote_asset,
            trade_date=position.close_time.date(),
        )
        ganancias_perdidas_futuros.append(
            {
                "position_id": position.position_id,
                "symbol": position.symbol,
                "side": position.side,
                "open_time": position.open_time.isoformat().replace("+00:00", "Z"),
                "close_time": position.close_time.isoformat().replace("+00:00", "Z"),
                "net_pnl_eur": _to_float(net_pnl_eur),
                "casilla": "332",
                "aviso_derivados": True,
            }
        )
    if ganancias_perdidas_futuros:
        avisos.append(
            "Futuros perpetuos: tratamiento fiscal como derivados puede diferir de transmision de moneda virtual. Confirmar con asesor."
        )

    base_assets = sorted(
        set(
            _filter_year(
                BrokerTrade.objects.filter(
                    credential__ownership=ownership,
                    side=BrokerTrade.Side.SELL,
                ),
                field="timestamp",
                year=year,
            ).values_list("base_asset", flat=True)
        )
    )
    ganancias_perdidas_trades: list[dict[str, Any]] = []
    fifo_has_gaps = False
    for base_asset in base_assets:
        fifo_result = calculate_fifo_for_asset(
            ownership=ownership,
            base_asset=base_asset,
            year=year,
            eur_converter=eur_converter,
        )
        sales = fifo_result["sales"]
        for warning in fifo_result["warnings"]:
            avisos.append(warning)
            fifo_has_gaps = True
        if not sales:
            continue
        valor_transmision = sum((Decimal(sale["proceeds_eur"]) for sale in sales), Decimal("0"))
        valor_adquisicion = sum(
            (
                sum(
                    (
                        Decimal(lot["cost_eur"]) + Decimal(lot["fee_eur_allocated"])
                        for lot in sale["matched_lots"]
                    ),
                    Decimal("0"),
                )
                for sale in sales
            ),
            Decimal("0"),
        )
        neto = valor_transmision - valor_adquisicion

        normalized_sales: list[dict[str, Any]] = []
        for sale in sales:
            normalized_sale = {
                **sale,
                "quantity_sold": float(Decimal(sale["quantity_sold"])),
                "proceeds_eur": _to_float(Decimal(sale["proceeds_eur"])),
                "fee_eur": _to_float(Decimal(sale["fee_eur"])),
                "gap_quantity": float(Decimal(sale["gap_quantity"])),
                "matched_lots": [],
            }
            for lot in sale["matched_lots"]:
                normalized_sale["matched_lots"].append(
                    {
                        **lot,
                        "quantity_consumed": float(Decimal(lot["quantity_consumed"])),
                        "unit_price_eur": _to_float(Decimal(lot["unit_price_eur"])),
                        "cost_eur": _to_float(Decimal(lot["cost_eur"])),
                        "fee_eur_allocated": _to_float(Decimal(lot["fee_eur_allocated"])),
                        "gain_loss_eur": _to_float(Decimal(lot["gain_loss_eur"])),
                    }
                )
            if sale.get("gap_reason"):
                avisos.append(
                    f"Gap FIFO en {base_asset} venta {sale['sell_trade_id']}: {sale['gap_reason']}."
                )
            normalized_sales.append(normalized_sale)

        ganancias_perdidas_trades.append(
            {
                "denominacion": base_asset,
                "casilla": "332",
                "valor_transmision_eur": _to_float(valor_transmision),
                "valor_adquisicion_eur": _to_float(valor_adquisicion),
                "ganancia_eur": _to_float(neto if neto > 0 else Decimal("0")),
                "perdida_eur": _to_float(abs(neto) if neto < 0 else Decimal("0")),
                "sales": normalized_sales,
            }
        )

    if base_assets and not fifo_has_gaps:
        avisos.append(
            "FIFO calculado cross-exchange (Pionex + Binance). Gaps de datos pueden afectar el calculo."
        )

    total_capital = sum(
        (Decimal(str(item["importe_eur"])) for item in capital_mobiliario), Decimal("0")
    )
    total_ganancias = Decimal("0")
    total_perdidas = Decimal("0")
    for section in ganancias_perdidas_trades:
        total_ganancias += Decimal(str(section["ganancia_eur"]))
        total_perdidas += Decimal(str(section["perdida_eur"]))
    for future in ganancias_perdidas_futuros:
        value = Decimal(str(future["net_pnl_eur"]))
        if value >= 0:
            total_ganancias += value
        else:
            total_perdidas += abs(value)

    trade_sources = set(
        BrokerTrade.objects.filter(credential__ownership=ownership).values_list("source", flat=True)
    )
    income_sources = set(income_qs.values_list("source", flat=True))
    futures_sources = set(
        FuturesPosition.objects.filter(credential__ownership=ownership).values_list(
            "source", flat=True
        )
    )

    data_sources = _build_data_sources(
        trade_sources=trade_sources,
        income_sources=income_sources,
        futures_sources=futures_sources,
    )

    reliability = _build_reliability(
        ownership=ownership,
        ganancias_perdidas_trades=ganancias_perdidas_trades,
        data_sources=data_sources,
    )

    # resumen_diagnostico: all trades including gap sales (full picture).
    resumen_diagnostico = {
        "total_capital_mobiliario_eur": _to_float(total_capital),
        "total_ganancias_eur": _to_float(total_ganancias),
        "total_perdidas_eur": _to_float(total_perdidas),
        "neto_ganancias_perdidas_eur": _to_float(total_ganancias - total_perdidas),
    }

    # resumen_declarable: only gap-free sales; null when status is blocked.
    blocked_statuses = {"blocked_missing_cost_basis", "blocked_unreconciled_balances"}
    if reliability["status"] in blocked_statuses:
        resumen_declarable = None
    else:
        resumen_declarable = _compute_resumen_declarable(
            ganancias_perdidas_trades=ganancias_perdidas_trades,
            ganancias_perdidas_futuros=ganancias_perdidas_futuros,
            total_capital=total_capital,
        )

    return {
        "schema_version": 3,
        "fiscal_year": year,
        "capital_mobiliario": capital_mobiliario,
        "ganancias_perdidas_bots": ganancias_perdidas_bots,
        "ganancias_perdidas_futuros": ganancias_perdidas_futuros,
        "ganancias_perdidas_trades": ganancias_perdidas_trades,
        "avisos": avisos,
        "data_sources": data_sources,
        "reliability": reliability,
        "resumen_diagnostico": resumen_diagnostico,
        "resumen_declarable": resumen_declarable,
        # backward-compatible alias kept for schema_version <3 consumers
        "resumen": resumen_diagnostico,
    }
