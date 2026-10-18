# Reusable helpers for the ERPNext deployment trackers (Vidira "Feature x PR x Date Map" and the
# GUIN "Feature x PR x Date Map"). Load the workbook with openpyxl, call these to append/insert
# release rows while preserving the existing cell styling, then wb.save(PATH) to the SAME path.
#
#   import sys; sys.path.insert(0, "<skill>/scripts")
#   from xlsx_helpers import (HEADER_FILL, header_style, status_fill, copy_row_style,
#                             write_row, find_legend_row, insert_map_rows, append_row, add_dated_sheet)

from copy import copy

from openpyxl.styles import Alignment, Font, PatternFill

# Current-Status fills used across every tracker.
GREEN = "FFC6EFCE"   # deployed & working
RED = "FFFFC7CE"     # reverted / not in prod
YELLOW = "FFEA9999"  # paused / in progress

# House header band (matches the 16-08-2026 sample): dark blue, bold white.
HEADER_HEX = "FF1F4E78"

# Defaults for the Vidira Deployment Map / dated-sheet schema. GUIN passes its own values.
STATUS_COL = 13
MAP_NCOLS = 16


def status_fill(kind="green"):
    hexval = {"green": GREEN, "red": RED, "yellow": YELLOW}[kind]
    return PatternFill(start_color=hexval, end_color=hexval, fill_type="solid")


def header_style(ws, ncols, row=1):
    # Paint the dark-blue bold-white header band + wrap, matching the house sample.
    fill = PatternFill(start_color=HEADER_HEX, end_color=HEADER_HEX, fill_type="solid")
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = fill
        cell.font = Font(bold=True, color="FFFFFFFF")
        cell.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def copy_row_style(ws, src_row, dst_row, ncols):
    # Clone every cell's style from src_row onto dst_row so inserted rows match the series.
    for c in range(1, ncols + 1):
        s = ws.cell(row=src_row, column=c)
        d = ws.cell(row=dst_row, column=c)
        if s.has_style:
            d.font = copy(s.font)
            d.fill = copy(s.fill)
            d.border = copy(s.border)
            d.alignment = copy(s.alignment)
            d.number_format = s.number_format
            d.protection = copy(s.protection)


def write_row(ws, row, values, ncols):
    for c in range(1, ncols + 1):
        ws.cell(row=row, column=c).value = values[c - 1] if c - 1 < len(values) else None


def find_legend_row(ws):
    # Deployment Map / dated sheets end with a "Legend:" (map) or "Features / bugs …" (dated) row.
    for r in range(1, ws.max_row + 1):
        v = ws.cell(row=r, column=1).value
        if v and str(v).startswith(("Legend:", "Features / bugs")):
            return r
    return ws.max_row + 1


def insert_map_rows(ws, recs, status_kinds=None, ncols=MAP_NCOLS, status_col=STATUS_COL):
    # Insert release rows before the trailing blank + legend row in the Deployment Map.
    legend = find_legend_row(ws)
    insert_at = legend - 1
    ws.insert_rows(insert_at, amount=len(recs))
    for i, rec in enumerate(recs):
        r = insert_at + i
        copy_row_style(ws, insert_at - 1, r, ncols)
        write_row(ws, r, rec, ncols)
        kind = (status_kinds or ["green"] * len(recs))[i]
        ws.cell(row=r, column=status_col).fill = status_fill(kind)
        ws.row_dimensions[r].height = ws.row_dimensions[insert_at - 1].height
    return insert_at


def append_row(ws, values, ncols):
    # Append one styled row at the bottom (used for All PRs task list and Deployments summary).
    base = ws.max_row
    copy_row_style(ws, base, base + 1, ncols)
    write_row(ws, base + 1, values, ncols)
    return base + 1


def add_dated_sheet(wb, prev_sheet_name, new_title, recs, footer_date, status_kinds=None,
                    ncols=MAP_NCOLS, status_col=STATUS_COL):
    # Clone the previous per-deploy dated sheet, wipe its data, write this release's rows + footer.
    src = wb[prev_sheet_name]
    new = wb.copy_worksheet(src)
    new.title = new_title
    for r in range(2, max(15, len(recs) + 4)):
        for c in range(1, ncols + 1):
            new.cell(row=r, column=c).value = None
            new.cell(row=r, column=c).fill = PatternFill(fill_type=None)
    for i, rec in enumerate(recs):
        r = 2 + i
        copy_row_style(new, 2, r, ncols)
        write_row(new, r, rec, ncols)
        kind = (status_kinds or ["green"] * len(recs))[i]
        new.cell(row=r, column=status_col).fill = status_fill(kind)
    footer_r = 2 + len(recs) + 1
    new.cell(row=footer_r, column=1).value = (
        f"Features / bugs / enhancements that went LIVE on {footer_date}. "
        "Reverted and pending items excluded."
    )
    copy_row_style(new, 2, footer_r, 1)
    return new
