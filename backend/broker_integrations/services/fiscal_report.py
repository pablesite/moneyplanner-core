from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.db.models import QuerySet

from memberships.models import Ownership

from ..models import BotNetResult, BrokerTrade, FuturesPosition, IncomeEvent
from .eur_converter import EurConverter
from .fifo_calculator import calculate_fifo_for_asset


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
        lots = fifo_result["lots"]
        for warning in fifo_result["warnings"]:
            avisos.append(warning)
            fifo_has_gaps = True
        if not lots:
            continue
        valor_transmision = sum((lot["proceeds_eur"] for lot in lots), Decimal("0"))
        valor_adquisicion = sum((lot["cost_eur"] for lot in lots), Decimal("0"))
        neto = valor_transmision - valor_adquisicion
        ganancias_perdidas_trades.append(
            {
                "denominacion": base_asset,
                "casilla": "332",
                "valor_transmision_eur": _to_float(valor_transmision),
                "valor_adquisicion_eur": _to_float(valor_adquisicion),
                "ganancia_eur": _to_float(neto if neto > 0 else Decimal("0")),
                "perdida_eur": _to_float(abs(neto) if neto < 0 else Decimal("0")),
                "lotes": [
                    {
                        **lot,
                        "quantity": float(Decimal(lot["quantity"])),
                        "cost_eur": _to_float(Decimal(lot["cost_eur"])),
                        "proceeds_eur": _to_float(Decimal(lot["proceeds_eur"])),
                        "gain_loss_eur": _to_float(Decimal(lot["gain_loss_eur"])),
                    }
                    for lot in lots
                ],
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

    return {
        "fiscal_year": year,
        "capital_mobiliario": capital_mobiliario,
        "ganancias_perdidas_bots": ganancias_perdidas_bots,
        "ganancias_perdidas_futuros": ganancias_perdidas_futuros,
        "ganancias_perdidas_trades": ganancias_perdidas_trades,
        "avisos": avisos,
        "data_sources": _build_data_sources(
            trade_sources=trade_sources,
            income_sources=income_sources,
            futures_sources=futures_sources,
        ),
        "resumen": {
            "total_capital_mobiliario_eur": _to_float(total_capital),
            "total_ganancias_eur": _to_float(total_ganancias),
            "total_perdidas_eur": _to_float(total_perdidas),
            "neto_ganancias_perdidas_eur": _to_float(total_ganancias - total_perdidas),
        },
    }
