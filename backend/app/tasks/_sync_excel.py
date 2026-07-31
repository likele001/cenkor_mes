"""同步 Excel 导出工具 — 用于小数据量列表的即时导出"""
from io import BytesIO

from openpyxl import Workbook
from fastapi.responses import StreamingResponse


def make_excel_response(headers: list[str], rows: list[list], filename: str, sheet_name: str = "Sheet1") -> StreamingResponse:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(headers)
    for row in rows:
        ws.append(row)
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
