"""Python batch port of focus4_out.cbl's product summary report."""

from __future__ import annotations

import argparse
import csv
import html
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


DESCRIPTION = "ELECTRONICS"
PRODUCT_COUNT_PER_RECORD = Decimal("1.00")
CENT = Decimal("0.01")
MAX_GROUPS = 1000
REQUIRED_COLUMNS = {"MAIN-KEY", "AMOUNT", "PROD-TYPE"}


@dataclass(frozen=True)
class MainRecord:
    key: str
    amount: Decimal
    product_type: str


@dataclass
class SummaryRow:
    description: str
    product_type: str
    amount: Decimal
    product_count: Decimal


def read_mainfile_csv(path: Path) -> list[MainRecord]:
    """Read a CSV export of MAINFILE; field names are case-insensitive."""
    records: list[MainRecord] = []
    with path.open("r", encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None:
            raise ValueError("MAINFILE CSV must have a header row.")

        headers = {name.strip().upper().replace("_", "-"): name for name in reader.fieldnames}
        missing = REQUIRED_COLUMNS - headers.keys()
        if missing:
            raise ValueError("MAINFILE CSV is missing columns: " + ", ".join(sorted(missing)))

        for line_number, row in enumerate(reader, start=2):
            key = (row.get(headers["MAIN-KEY"]) or "").strip()
            product_type = (row.get(headers["PROD-TYPE"]) or "").strip()
            amount_text = (row.get(headers["AMOUNT"]) or "").strip()
            if not key or not product_type or not amount_text:
                raise ValueError(f"CSV line {line_number}: key, amount, and product type are required.")
            if len(key) > 10:
                raise ValueError(f"CSV line {line_number}: MAIN-KEY exceeds PIC X(10).")
            if len(product_type) > 20:
                raise ValueError(f"CSV line {line_number}: PROD-TYPE exceeds PIC X(20).")
            try:
                amount = Decimal(amount_text)
            except InvalidOperation as error:
                raise ValueError(f"CSV line {line_number}: AMOUNT is not a valid decimal.") from error
            if not amount.is_finite():
                raise ValueError(f"CSV line {line_number}: AMOUNT must be finite.")
            if amount != amount.quantize(CENT):
                raise ValueError(f"CSV line {line_number}: AMOUNT supports at most two decimal places.")
            records.append(MainRecord(key, amount, product_type))
    return records


def aggregate_records(records: list[MainRecord]) -> list[SummaryRow]:
    """Apply the source program's fixed description and product-type grouping."""
    summaries: dict[tuple[str, str], SummaryRow] = {}
    for record in records:
        group_key = (DESCRIPTION, record.product_type)
        if group_key in summaries:
            summary = summaries[group_key]
            summary.amount += record.amount
            summary.product_count += PRODUCT_COUNT_PER_RECORD
            continue
        if len(summaries) >= MAX_GROUPS:
            raise ValueError("ERROR: SUMMARY TABLE OVERFLOW (maximum 1000 groups).")
        summaries[group_key] = SummaryRow(
            description=DESCRIPTION,
            product_type=record.product_type,
            amount=record.amount,
            product_count=PRODUCT_COUNT_PER_RECORD,
        )
    return list(summaries.values())


def render_report(rows: list[SummaryRow]) -> str:
    """Build the HTML report written by the COBOL program."""
    if not rows:
        raise ValueError("NO RECORDS FOUND FOR REPORT")

    style = """<style type="text/css">
table {border-collapse: collapse; font-family: Arial; font-size: 10pt;}
th {background-color: blue; color: white; font-weight: bold; text-align: center;}
td, th {border: 1px solid black; padding: 5px;}
</style>"""
    lines = [
        '<html xmlns:o="urn:schemas-microsoft-com:office:office"',
        'xmlns:x="urn:schemas-microsoft-com:office:excel"',
        'xmlns="http://www.w3.org/TR/REC-html40">',
        "<head>",
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">',
        style,
        "</head>",
        "<body>",
        '<h2 style="color:blue;font-family:Arial;">SUMMARY_REPORT</h2>',
        "<table>",
        "<tr><th>DESCRIPTION</th><th>PROD_TYPE</th><th>AMOUNT</th><th>PRODUCT_COUNT</th></tr>",
    ]
    for row in rows:
        lines.append(
            "<tr>"
            f"<td>{html.escape(row.description)}</td>"
            f"<td>{html.escape(row.product_type)}</td>"
            f'<td align="right">{row.amount:.2f}</td>'
            f'<td align="right">{row.product_count:.2f}</td>'
            "</tr>"
        )
    lines.extend(["</table>", "</body>", "</html>"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Python port of focus4_out.cbl using a CSV export of MAINFILE."
    )
    parser.add_argument("mainfile_csv", type=Path, help="CSV with MAIN-KEY, AMOUNT, and PROD-TYPE columns")
    parser.add_argument("output_html", type=Path, help="path for the generated HTML report")
    arguments = parser.parse_args()

    try:
        records = read_mainfile_csv(arguments.mainfile_csv)
        rows = aggregate_records(records)
        report = render_report(rows)
        arguments.output_html.write_text(report, encoding="utf-8", newline="\n")
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1

    print(f"REPORT GENERATED SUCCESSFULLY WITH {len(rows)} RECORDS")
    print(f"Wrote {arguments.output_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())