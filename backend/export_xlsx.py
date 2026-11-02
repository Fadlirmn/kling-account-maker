"""
Export akun ke workbook xlsx (openpyxl write_only): satu sheet "accounts",
header tebal, lebar kolom menyesuaikan isi (dibatasi 60 karakter).
"""

from __future__ import annotations

import io
import json
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

_MAX_WIDTH = 60


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, bool):
        return "ya" if v else "tidak"
    return v


def accounts_workbook(rows: list[dict], sheet_title: str = "accounts") -> bytes:
    wb = Workbook(write_only=True)
    ws = wb.create_sheet(title=sheet_title[:31])
    cols = list(rows[0].keys()) if rows else ["email", "status"]
    widths = {i: len(c) for i, c in enumerate(cols)}
    header = []
    for c in cols:
        cell = ws.cell if False else None  # write_only: pakai WriteOnlyCell lewat append
        header.append(c)
    from openpyxl.cell import WriteOnlyCell
    hcells = []
    for c in header:
        wc = WriteOnlyCell(ws, value=c)
        wc.font = Font(bold=True)
        hcells.append(wc)
    ws.append(hcells)
    for r in rows:
        vals = [_cell(r.get(c)) for c in cols]
        for i, v in enumerate(vals):
            widths[i] = max(widths[i], min(_MAX_WIDTH, len(str(v))))
        ws.append(vals)
    for i, w in widths.items():
        ws.column_dimensions[get_column_letter(i + 1)].width = w + 2
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
