# -*- coding: utf-8 -*-
"""
Markdown table utility functions.
"""
import re
from typing import List, Tuple

from openpyxl import Workbook


def _strp_cell(cell):
    val = cell.strip()
    if val == "":
        return None

    return val


def _extract_array(mdtablerow):
    match = re.match(r"\s*\|(.*)\|\s*", mdtablerow)
    if match:
        mtchstr = match.groups()[0]
        if re.match(r"^[\|-]+$", mtchstr):
            return False
        return [_strp_cell(c) for c in mtchstr.split("|")]

    return False


def _is_null_row(r_arr):
    for cell in r_arr:
        if cell is not None:
            return False

    return True


def md_table_to_ss_structure(mdstr: str) -> List[Tuple[str, List[List[str]]]]:
    """Transform markdown to an ss structure"""
    ss_arr = []
    for item in mdstr.split("\n"):
        arr = _extract_array(item)
        if arr:
            ss_arr.append(arr)
    sheet_name = False
    sheet_arr = False
    sheets = []
    for row in ss_arr:
        if row[0] is not None:
            if sheet_arr:
                sheets.append((sheet_name, sheet_arr))
            sheet_arr = []
            sheet_name = row[0]
        excluding_first_col = row[1:]
        if sheet_name and not _is_null_row(excluding_first_col):
            sheet_arr.append(excluding_first_col)
    sheets.append((sheet_name, sheet_arr))

    return sheets


def md_table_to_workbook(mdstr: str) -> Workbook:
    """
    Convert Markdown table string to an openpyxl.Workbook. Call workbook.save() to
    persist.
    """
    md_data = md_table_to_ss_structure(mdstr=mdstr)
    workbook = Workbook(write_only=True)
    for key, rows in md_data:
        sheet = workbook.create_sheet(title=key)
        for row in rows:
            sheet.append(row)
    return workbook
