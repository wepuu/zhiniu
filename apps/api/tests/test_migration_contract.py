from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from zhaoniu_api.system import MIGRATION_HEAD

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_application_migration_head_matches_alembic_head() -> None:
    config = Config(str(REPOSITORY_ROOT / "infrastructure" / "migrations" / "alembic.ini"))
    config.set_main_option(
        "script_location",
        str(REPOSITORY_ROOT / "infrastructure" / "migrations"),
    )

    assert ScriptDirectory.from_config(config).get_heads() == [MIGRATION_HEAD]
