"""Excel download serialisation: identifiers are literal text, not numbers/formulas."""

import io
import re
from decimal import Decimal, InvalidOperation

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import IllegalCharacterError

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def excel_number(value):
    """Only explicitly numeric columns can become finite, lossless Excel numbers."""
    raw = value.strip()
    if any(separator in raw for separator in ("’", "'", "\u202f")) and not re.fullmatch(r"-?\d{1,3}(?:[’'\u202f]\d{3})+(?:\.\d+)?", raw):
        return None
    normal = value.replace("’", "").replace("'", "").replace("\u202f", "").strip()
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", normal):
        return None
    integer_part = normal.lstrip("-").split(".")[0]
    if len(integer_part) > 1 and integer_part.startswith("0"):
        return None
    try:
        number = Decimal(normal)
    except InvalidOperation:
        return None
    # Excel has 15 significant digits. Retain larger values as exact text.
    if not number.is_finite() or len(number.as_tuple().digits) > 15:
        return None
    return int(number) if number == number.to_integral_value() else number


def identifier_column(column):
    key = column.get("key", "").lower()
    label = column["label"].split("·", 1)[0].strip().lower()
    return key in {"gtin", "gtin14", "gln", "serial_number", "source_code", "obp_id"} or label in {
        "gtin", "gtin14", "gln", "serial", "serial number", "batch id", "batch code",
        "product code", "obp id", "emvs mah id", "organisation id", "location id",
    }


def excel_bytes(columns, rows):
    # Reject unsupported source values rather than silently truncate/replace them.
    for values in ([column["label"] for column in columns], *rows):
        for value in values:
            if len(value) > 32767 or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value):
                raise ValueError("A source value cannot be represented fully in Excel. Use Download CSV instead.")
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("View")
    sheet.freeze_panes = "A2"
    for index, column in enumerate(columns, 1):
        width = max(len(column["label"]), *(len(row[index - 1].split("\n")[0]) for row in rows[:100]), 14)
        sheet.column_dimensions[get_column_letter(index)].width = min(width + 2, 60)
    headers = []
    for column in columns:
        cell = WriteOnlyCell(sheet, value=column["label"])
        cell.data_type = "s"
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2261B4")
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        headers.append(cell)
    sheet.append(headers)
    try:
        for row in rows:
            cells = []
            for column, value in zip(columns, row, strict=True):
                number = excel_number(value) if column.get("type") == "number" and not identifier_column(column) else None
                if number is not None:
                    cell = WriteOnlyCell(sheet, value=number)
                    cell.number_format = "#,##0" if isinstance(number, int) else "#,##0.###############"
                else:
                    cell = WriteOnlyCell(sheet, value=value)
                    cell.data_type = "s"  # Also prevents =... from becoming an Excel formula.
                    cell.number_format = "@"
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                cells.append(cell)
            sheet.append(cells)
        sheet.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{len(rows) + 1}"
        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue()
    except IllegalCharacterError as exc:
        raise ValueError("A source value is not supported by Excel. Use Download CSV instead.") from exc
    finally:
        workbook.close()
