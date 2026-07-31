"""系统内置打印模板（按租户 code 幂等创建）"""

TASK_LABEL_HTML = """<html><head><meta charset="utf-8" />
<style>@page{size:60mm 40mm;margin:2mm}
body{font-family:Arial,Helvetica,sans-serif;font-size:12px}
.box{display:flex;gap:6mm;align-items:center}
.qr{width:26mm;height:26mm}
.t{line-height:1.4}
.code{font-weight:700;font-size:14px}
</style></head><body>
<div class="box">
<div class="qr">{{ qr.svg }}</div>
<div class="t">
<div class="code">{{ task.task_code }}</div>
<div>工序：{{ process.code }} {{ process.name }}</div>
<div>型号：{{ sku.code }} {{ sku.name }}</div>
<div>工单：#{{ work_order.id }} 计划：{{ task.planned_qty }}</div>
</div></div></body></html>"""

DEFAULT_PRINT_TEMPLATES: list[tuple[str, str, str, str]] = [
    # code, name, template_type, content
    ("task_label", "任务码标签", "html", TASK_LABEL_HTML),
]
