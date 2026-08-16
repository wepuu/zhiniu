import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from zhaoniu_api.main import create_app  # noqa: E402

PACKAGE = ROOT / "packages" / "api-client"
OPENAPI = PACKAGE / "openapi.json"
SCHEMA = PACKAGE / "src" / "schema.d.ts"
expected_openapi = json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n"

with tempfile.TemporaryDirectory(prefix="zhaoniu-openapi-") as directory:
    temp_openapi = Path(directory) / "openapi.json"
    temp_schema = Path(directory) / "schema.d.ts"
    temp_openapi.write_text(expected_openapi, encoding="utf-8")
    executable = (
        PACKAGE
        / "node_modules"
        / ".bin"
        / ("openapi-typescript.cmd" if os.name == "nt" else "openapi-typescript")
    )
    subprocess.run(
        [str(executable), str(temp_openapi), "-o", str(temp_schema)],
        cwd=PACKAGE,
        check=True,
    )
    if OPENAPI.read_text(encoding="utf-8") != expected_openapi:
        raise SystemExit("OpenAPI JSON drift detected; run pnpm api:generate")
    if SCHEMA.read_text(encoding="utf-8") != temp_schema.read_text(encoding="utf-8"):
        raise SystemExit("Generated TypeScript drift detected; run pnpm api:generate")
