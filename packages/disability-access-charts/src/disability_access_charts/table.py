"""The data-table fallback as HTML or CSV.

Every chart document carries a ``table`` (caption, columns, rows). :func:`to_html` writes
it as an accessible table: a ``<caption>``, column headers with ``scope="col"``, and the
first cell of each row as a row header with ``scope="row"``. :func:`to_csv` writes the raw
values, unformatted, for download.
"""

from __future__ import annotations

import csv
import html
import io
from collections.abc import Mapping
from typing import Any


def _table(doc_or_table: Mapping[str, Any]) -> Mapping[str, Any]:
    return doc_or_table.get("table", doc_or_table)


def format_cell(value: Any, column: Mapping[str, Any]) -> str:
    """A cell as the page shows it, matching the site's ``format.js``."""
    kind = column.get("type", "text")
    if value is None:
        return ""
    if kind == "integer":
        return f"{round(value):,}"
    if kind == "percent":
        return f"{value:.1f}"
    if kind == "number":
        return f"{value:,.{int(column.get('decimals', 1))}f}"
    return str(value)


def to_html(doc_or_table: Mapping[str, Any]) -> str:
    """The table as an HTML ``<table>`` string, with every value escaped."""
    table = _table(doc_or_table)
    columns = table["columns"]
    lines = ["<table>", f"  <caption>{html.escape(table['caption'])}</caption>", "  <thead>"]

    def num(column: Mapping[str, Any]) -> str:
        return "" if column.get("type", "text") == "text" else ' class="num"'

    head = "".join(f'<th scope="col"{num(c)}>{html.escape(c["label"])}</th>' for c in columns)
    lines += [f"    <tr>{head}</tr>", "  </thead>", "  <tbody>"]
    for row in table["rows"]:
        cells = []
        for i, (value, column) in enumerate(zip(row, columns, strict=True)):
            text = html.escape(format_cell(value, column))
            if i == 0:
                cells.append(f'<th scope="row"{num(column)}>{text}</th>')
            else:
                cells.append(f"<td{num(column)}>{text}</td>")
        lines.append(f"    <tr>{''.join(cells)}</tr>")
    lines += ["  </tbody>", "</table>"]
    return "\n".join(lines) + "\n"


def to_csv(doc_or_table: Mapping[str, Any]) -> str:
    """The table as CSV: a header row of column labels, then the raw values."""
    table = _table(doc_or_table)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow([c["label"] for c in table["columns"]])
    for row in table["rows"]:
        writer.writerow(["" if v is None else v for v in row])
    return out.getvalue()
