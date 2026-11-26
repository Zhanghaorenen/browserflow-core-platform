import csv
import io
import json


def render_result(data, format_type):
    if format_type == "json":
        return json.dumps(data, ensure_ascii=False, indent=2).encode(
            "utf-8"
        ), "application/json"
    if format_type != "csv":
        raise ValueError("不支持的导出格式")
    rows = data.get("items", [])
    fields = list(dict.fromkeys(key for row in rows for key in row))
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()

    def safe(value):
        text = str(value)
        return (
            "'" + text
            if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
            else text
        )

    writer.writerows({key: safe(value) for key, value in row.items()} for row in rows)
    return ("\ufeff" + buffer.getvalue()).encode("utf-8"), "text/csv"
