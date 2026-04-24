from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _ratio_part(*, total: Decimal, part: Decimal, whole: Decimal) -> Decimal:
    if whole == 0:
        return Decimal("0")
    return total * part / whole


def _fmt_money(value: Any) -> str:
    return f"{_to_decimal(value):.2f}"


def _fmt_qty(value: Any) -> str:
    return f"{_to_decimal(value):f}"


def _csv_origin_for_lot(lot: dict[str, Any]) -> str:
    if lot.get("manual_cost_basis_id"):
        return "manual_cost_basis"
    if lot.get("buy_trade_id"):
        return "trade"
    return "trade"


def export_csv(report: dict[str, Any]) -> bytes:
    """Generate CSV with one row per consumed lot (AEAT-friendly columns)."""
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "denominacion",
            "fecha_adquisicion",
            "exchange_adquisicion",
            "fecha_transmision",
            "exchange_transmision",
            "cantidad",
            "valor_adquisicion_eur",
            "valor_transmision_eur",
            "comision_eur",
            "ganancia_perdida_eur",
            "dias_tenencia",
            "origen_coste",
        ]
    )

    for section in report.get("ganancias_perdidas_trades", []):
        denominacion = section.get("denominacion", "")
        for sale in section.get("sales", []):
            quantity_sold = _to_decimal(sale.get("quantity_sold"))
            proceeds_eur = _to_decimal(sale.get("proceeds_eur"))
            fee_eur = _to_decimal(sale.get("fee_eur"))
            sell_date = sale.get("sell_date", "")
            sell_exchange = sale.get("sell_exchange", "")

            for lot in sale.get("matched_lots", []):
                quantity_consumed = _to_decimal(lot.get("quantity_consumed"))
                writer.writerow(
                    [
                        denominacion,
                        lot.get("buy_date") or "N/A",
                        lot.get("buy_exchange") or "N/A",
                        sell_date,
                        sell_exchange,
                        _fmt_qty(quantity_consumed),
                        _fmt_money(lot.get("cost_eur")),
                        _fmt_money(
                            _ratio_part(
                                total=proceeds_eur,
                                part=quantity_consumed,
                                whole=quantity_sold,
                            )
                        ),
                        _fmt_money(lot.get("fee_eur_allocated")),
                        _fmt_money(lot.get("gain_loss_eur")),
                        lot.get("hold_days", 0),
                        _csv_origin_for_lot(lot),
                    ]
                )

            gap_quantity = _to_decimal(sale.get("gap_quantity"))
            if gap_quantity <= 0:
                continue
            gap_fee_eur = _ratio_part(total=fee_eur, part=gap_quantity, whole=quantity_sold)
            gap_proceeds_eur = _ratio_part(
                total=proceeds_eur, part=gap_quantity, whole=quantity_sold
            )
            writer.writerow(
                [
                    denominacion,
                    "N/A",
                    "N/A",
                    sell_date,
                    sell_exchange,
                    _fmt_qty(gap_quantity),
                    _fmt_money(Decimal("0")),
                    _fmt_money(gap_proceeds_eur),
                    _fmt_money(gap_fee_eur),
                    _fmt_money(gap_proceeds_eur - gap_fee_eur),
                    "N/A",
                    f"gap:{sale.get('gap_reason') or 'missing_data'}",
                ]
            )

    return output.getvalue().encode("utf-8")


def _append_title(story: list[Any], text: str) -> None:
    styles = getSampleStyleSheet()
    story.append(Paragraph(text, styles["Heading2"]))
    story.append(Spacer(1, 8))


def _append_table(story: list[Any], data: list[list[Any]]) -> None:
    table = Table(data, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 12))


def export_pdf(report: dict[str, Any]) -> bytes:
    """Generate a readable annual PDF fiscal report dossier."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title="Informe fiscal crypto",
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
    )
    styles = getSampleStyleSheet()
    story: list[Any] = []
    year = report.get("fiscal_year", "")

    story.append(Paragraph(f"Informe Fiscal Crypto {year}", styles["Title"]))
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "Borrador de apoyo; no sustituye validacion fiscal profesional.",
            styles["Italic"],
        )
    )
    story.append(Spacer(1, 16))

    resumen = report.get("resumen", {})
    _append_title(story, "Resumen")
    _append_table(
        story,
        [
            ["Campo", "Importe EUR"],
            [
                "Capital mobiliario (casilla 029)",
                _fmt_money(resumen.get("total_capital_mobiliario_eur")),
            ],
            ["Ganancias (casilla 332)", _fmt_money(resumen.get("total_ganancias_eur"))],
            ["Perdidas (casilla 332)", _fmt_money(resumen.get("total_perdidas_eur"))],
            ["Neto ganancias/perdidas", _fmt_money(resumen.get("neto_ganancias_perdidas_eur"))],
        ],
    )

    _append_title(story, "Ganancias/Perdidas por Asset (FIFO)")
    for section in report.get("ganancias_perdidas_trades", []):
        asset = section.get("denominacion", "")
        story.append(Paragraph(f"Asset: {asset}", styles["Heading3"]))
        story.append(Spacer(1, 6))
        _append_table(
            story,
            [
                ["Valor transmision", "Valor adquisicion", "Ganancia", "Perdida"],
                [
                    _fmt_money(section.get("valor_transmision_eur")),
                    _fmt_money(section.get("valor_adquisicion_eur")),
                    _fmt_money(section.get("ganancia_eur")),
                    _fmt_money(section.get("perdida_eur")),
                ],
            ],
        )
        rows = [
            [
                "Venta",
                "Fecha venta",
                "Fecha compra",
                "Exchange compra",
                "Cantidad",
                "Coste EUR",
                "Comision EUR",
                "G/P EUR",
                "Origen",
            ]
        ]
        for sale in section.get("sales", []):
            sale_id = sale.get("sell_trade_id", "")
            for lot in sale.get("matched_lots", []):
                rows.append(
                    [
                        sale_id,
                        sale.get("sell_date", ""),
                        lot.get("buy_date") or "N/A",
                        lot.get("buy_exchange") or "N/A",
                        _fmt_qty(lot.get("quantity_consumed")),
                        _fmt_money(lot.get("cost_eur")),
                        _fmt_money(lot.get("fee_eur_allocated")),
                        _fmt_money(lot.get("gain_loss_eur")),
                        _csv_origin_for_lot(lot),
                    ]
                )
            gap_quantity = _to_decimal(sale.get("gap_quantity"))
            if gap_quantity > 0:
                quantity_sold = _to_decimal(sale.get("quantity_sold"))
                proceeds_eur = _to_decimal(sale.get("proceeds_eur"))
                fee_eur = _to_decimal(sale.get("fee_eur"))
                gap_fee = _ratio_part(total=fee_eur, part=gap_quantity, whole=quantity_sold)
                gap_proceeds = _ratio_part(
                    total=proceeds_eur, part=gap_quantity, whole=quantity_sold
                )
                rows.append(
                    [
                        sale_id,
                        sale.get("sell_date", ""),
                        "N/A",
                        "N/A",
                        _fmt_qty(gap_quantity),
                        "0.00",
                        _fmt_money(gap_fee),
                        _fmt_money(gap_proceeds - gap_fee),
                        f"gap:{sale.get('gap_reason') or 'missing_data'}",
                    ]
                )
        _append_table(story, rows)

    _append_title(story, "Capital mobiliario")
    capital_rows = [["Fuente", "Asset", "Importe EUR", "Casilla"]]
    for row in report.get("capital_mobiliario", []):
        capital_rows.append(
            [
                row.get("fuente", ""),
                row.get("asset", ""),
                _fmt_money(row.get("importe_eur")),
                row.get("casilla", ""),
            ]
        )
    _append_table(story, capital_rows)

    _append_title(story, "Conciliacion bots")
    bots_rows = [["Bot", "Tipo", "Periodo", "Ganancia neta EUR", "Casilla"]]
    for row in report.get("ganancias_perdidas_bots", []):
        bots_rows.append(
            [
                row.get("bot_label", ""),
                row.get("bot_type", ""),
                row.get("periodo", ""),
                _fmt_money(row.get("ganancia_neta_eur")),
                row.get("casilla", ""),
            ]
        )
    _append_table(story, bots_rows)

    _append_title(story, "Avisos")
    avisos = report.get("avisos", [])
    if avisos:
        for aviso in avisos:
            story.append(Paragraph(f"- {aviso}", styles["BodyText"]))
            story.append(Spacer(1, 2))
    else:
        story.append(Paragraph("- Sin avisos.", styles["BodyText"]))

    doc.build(story)
    return buffer.getvalue()
