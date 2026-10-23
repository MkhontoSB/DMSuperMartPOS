"""Barcode validation and PDF generation for the SuperMart API."""
from __future__ import annotations

import io
import re
from decimal import Decimal
from typing import Iterable

from reportlab.graphics.barcode import eanbc, widgets
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle


def ean13_checksum(code_str: str) -> str:
    """Return the EAN-13 check digit for exactly 12 ASCII numeric digits."""
    if not isinstance(code_str, str) or len(code_str) != 12:
        raise ValueError("EAN-13 input must contain exactly 12 digits.")
    if not code_str.isascii() or not code_str.isdigit():
        raise ValueError("EAN-13 input must contain only numeric digits.")
    digits = [int(digit) for digit in code_str]
    checksum = (10 - (sum(digits[::2]) + sum(digits[1::2]) * 3) % 10) % 10
    return code_str + str(checksum)


def _validated_ean13(value: str) -> str:
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        raise ValueError("EAN-13 barcode must contain numeric digits only.")
    if len(value) == 12:
        return ean13_checksum(value)
    if len(value) == 13 and ean13_checksum(value[:12]) == value:
        return value
    raise ValueError("EAN-13 barcode must be 12 digits (base) or a valid 13-digit EAN-13 code.")


def _barcode_drawing(value: str, barcode_type: str) -> Drawing:
    drawing = Drawing(190, 52)
    if barcode_type == "EAN-13":
        barcode = eanbc.Ean13BarcodeWidget(_validated_ean13(value), barHeight=32, barWidth=1)
    elif barcode_type == "Code 39":
        cleaned = re.sub(r"[^A-Z0-9\-\.\$\/\+\%\s]", "", value.upper())
        if not cleaned.strip():
            raise ValueError("Value has no characters supported by Code 39.")
        barcode = widgets.BarcodeStandard39(value=cleaned, barHeight=32, barWidth=1, humanReadable=True)
    else:
        raise ValueError("barcode_type must be 'EAN-13' or 'Code 39'.")
    drawing.add(barcode)
    return drawing


def generate_barcode_pdf(items: Iterable[dict], barcode_type: str, copies_per_item: int = 1) -> bytes:
    """Build a PDF of labels in memory; no filesystem writes are performed."""
    if barcode_type not in {"EAN-13", "Code 39"}:
        raise ValueError("barcode_type must be 'EAN-13' or 'Code 39'.")
    if isinstance(copies_per_item, bool) or not isinstance(copies_per_item, int) or not 1 <= copies_per_item <= 100:
        raise ValueError("copies_per_item must be between 1 and 100.")

    labels = []
    styles = getSampleStyleSheet()
    for item in items:
        value = str(item.get("barcode") or item.get("item_id") or "")
        if not value:
            raise ValueError(f"Product {item.get('item_id', '')!r} has no barcode or item ID.")
        name = str(item.get("name") or item.get("item_id") or "Product")[:60]
        price = item.get("selling_price")
        try:
            price_text = f"R{Decimal(str(price or 0)):.2f}"
        except Exception:
            price_text = ""
        drawing = _barcode_drawing(value, barcode_type)
        for _ in range(copies_per_item):
            labels.append([Paragraph(name.replace("&", "&amp;").replace("<", "&lt;"), styles["Normal"]), drawing, Paragraph(price_text, styles["Normal"])])

    if not labels:
        raise ValueError("Select at least one product to generate labels.")

    rows = [labels[index:index + 3] for index in range(0, len(labels), 3)]
    for row in rows:
        while len(row) < 3:
            row.append("")
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18, rightMargin=18, topMargin=24, bottomMargin=24)
    table = Table(rows, colWidths=[180, 180, 180], rowHeights=84, repeatRows=0)
    table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]))
    doc.build([table])
    return buffer.getvalue()
