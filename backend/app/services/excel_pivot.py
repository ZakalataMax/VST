from __future__ import annotations

from pathlib import Path

XL_DATABASE = 1
XL_ROW_FIELD = 1
XL_COUNT = -4112
XL_PERCENT_OF_TOTAL = 8

PIVOT_VERSION = 8
PIVOT_STYLE = "PivotStyleLight16"


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
            "% of total",
            XL_COUNT,
        )
        percent_field.Calculation = XL_PERCENT_OF_TOTAL
        workbook.Save()
    finally:
        if workbook is not None:
            workbook.Close(SaveChanges=True)
        if excel is not None:
            excel.Quit()
        pythoncom.CoUninitialize()


def add_pivot_sheet(
    workbook,
    *,
    columns: list[str],
    total: int,
    row_fields: list[str],
    value_field: str,
    data_sheet: str = "Data",
    pivot_sheet: str = "Pivot",
) -> bool:
    from openpyxl.pivot.cache import (
        CacheDefinition,
        CacheField,
        CacheSource,
        SharedItems,
        WorksheetSource,
    )
    from openpyxl.pivot.record import RecordList
    from openpyxl.pivot.table import (
        DataField,
        Location,
        PivotField,
        PivotTableStyle,
        RowColField,
        TableDefinition,
    )

    if value_field not in columns or total <= 0:
        return False
    if not row_fields or any(field not in columns for field in row_fields):
        return False

    row_indexes = [columns.index(field) for field in row_fields]
    value_index = columns.index(value_field)
    last_col = _column_letter(len(columns))
    source_ref = f"A1:{last_col}{total + 1}"

    cache = CacheDefinition(
        cacheSource=CacheSource(
            type="worksheet",
            worksheetSource=WorksheetSource(ref=source_ref, sheet=data_sheet),
        ),
        cacheFields=[CacheField(name=name, sharedItems=SharedItems()) for name in columns],
        refreshOnLoad=True,
        refreshedBy="VST",
        createdVersion=PIVOT_VERSION,
        refreshedVersion=PIVOT_VERSION,
        minRefreshableVersion=3,
        recordCount=total,
    )
    cache.records = RecordList()

    row_index_set = set(row_indexes)
    pivot_fields: list[PivotField] = []
    for index in range(len(columns)):
        is_row = index in row_index_set
        is_data = index == value_index
        if is_row and is_data:
            pivot_fields.append(PivotField(axis="axisRow", dataField=True, showAll=False))
        elif is_row:
            pivot_fields.append(PivotField(axis="axisRow", showAll=False))
        elif is_data:
            pivot_fields.append(PivotField(dataField=True, showAll=False))
        else:
            pivot_fields.append(PivotField(showAll=False))

    pivot_ws = workbook.create_sheet(pivot_sheet)
    table = TableDefinition(
        name="ReportPivot",
        cacheId=1,
        dataCaption="Values",
        location=Location(ref="A3:C6", firstHeaderRow=1, firstDataRow=2, firstDataCol=1),
        pivotFields=pivot_fields,
        rowFields=[RowColField(x=index) for index in row_indexes],
        colFields=[RowColField(x=-2)],
        dataFields=[
            DataField(name="Count", fld=value_index, subtotal="count", baseField=0, baseItem=0),
            DataField(
                name="% of total",
                fld=value_index,
                subtotal="count",
                showDataAs="percentOfTotal",
                baseField=0,
                baseItem=0,
            ),
        ],
        pivotTableStyleInfo=PivotTableStyle(
            name=PIVOT_STYLE,
            showRowHeaders=True,
            showColHeaders=True,
            showRowStripes=False,
            showColStripes=False,
            showLastColumn=True,
        ),
        updatedVersion=PIVOT_VERSION,
        minRefreshableVersion=3,
        createdVersion=PIVOT_VERSION,
        indent=0,
        outline=True,
        outlineData=True,
        multipleFieldFilters=False,
    )
    table.cache = cache
    pivot_ws.add_pivot(table)
    return True
