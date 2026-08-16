import json
from pathlib import Path

from zhaoniu_api.main import app


def main() -> None:
    output = Path("packages/api-client/openapi.json")
    output.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
