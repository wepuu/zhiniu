import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from zhaoniu_api.main import create_app  # noqa: E402

TARGET = ROOT / "packages" / "api-client" / "openapi.json"
TARGET.write_text(
    json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
