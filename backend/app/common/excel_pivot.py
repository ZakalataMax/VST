from __future__ import annotations

from pathlib import Path

XL_DATABASE = 1
XL_ROW_FIELD = 1
XL_COUNT = -4112
XL_PERCENT_OF_PARENT_ROW = 10


def _column_letter(index_one_based: int) -> str:
    letters = ""
    number = index_one_based
    while number > 0:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def native_pivot_available() -> bool:
    try:
        import win32com.client  # noqa: F401
    except Exception:
        return False
    return True


def add_native_pivot(
    xlsx_path: str | Path,
    *,
    data_sheet: str,
    data_rows: int,
    data_cols: int,
    row_fields: list[str],
    value_field: str,
    pivot_sheet: str = "Pivot",
) -> None:
    import pythoncom
    import win32com.client as win32

    path = str(Path(xlsx_path).resolve())
    last_col = _column_letter(data_cols)
    last_row = data_rows + 1

    pythoncom.CoInitialize()
    excel = None
    workbook = None
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        workbook = excel.Workbooks.Open(path)
        data_ws = workbook.Worksheets(data_sheet)
        source = data_ws.Range(f"A1:{last_col}{last_row}")
        cache = workbook.PivotCaches().Create(
            SourceType=XL_DATABASE,
            SourceData=source,
        )
        pivot_ws = workbook.Worksheets.Add()
        pivot_ws.Name = pivot_sheet
        table = cache.CreatePivotTable(
            TableDestination=pivot_ws.Range("A3"),
            TableName="ReportPivot",
        )
        for position, field in enumerate(row_fields, start=1):
            pivot_field = table.PivotFields(field)
            pivot_field.Orientation = XL_ROW_FIELD
            pivot_field.Position = position
        table.AddDataField(
            table.PivotFields(value_field),
            "Count",
            XL_COUNT,
        )
        percent_field = table.AddDataField(
            table.PivotFields(value_field),
            "% of parent",
            XL_COUNT,
        )
        percent_field.Calculation = XL_PERCENT_OF_PARENT_ROW
        workbook.Save()
    finally:
        if workbook is not None:
            workbook.Close(SaveChanges=True)
        if excel is not None:
            excel.Quit()
        pythoncom.CoUninitialize()
