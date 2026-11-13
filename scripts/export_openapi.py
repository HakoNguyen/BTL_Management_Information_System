"""Ghi OpenAPI của api ra file JSON, không cần chạy server hay CSDL.

Dùng: python scripts/export_openapi.py web/openapi.json  (make gen-api gọi lệnh này)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO_ROOT), str(REPO_ROOT / "api")]

from main import app  # noqa: E402

output = Path(sys.argv[1])
# sort_keys: nội dung ổn định giữa các lần chạy, để schema.d.ts chỉ đổi khi API đổi
output.write_text(
    json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
# Chỉ in ASCII: console Windows không in được dấu tiếng Việt với bảng mã mặc định
print(f"OpenAPI -> {output}")
