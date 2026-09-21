from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_module() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[3]
        / "infrastructure"
        / "production"
        / "phase25h-configuration-fingerprint.py"
    )
    spec = importlib.util.spec_from_file_location("phase25h_configuration_fingerprint", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


fingerprints = _load_module()


def test_configuration_fingerprint_is_deterministic_and_excludes_secrets(tmp_path: Path) -> None:
    first = tmp_path / "first.env"
    second = tmp_path / "second.env"
    first.write_text(
        "APP_ENV=production\nRESEND_API_KEY=secret-one\nAUTOMATION_HARD_DISABLED=false\n",
        encoding="utf-8",
    )
    second.write_text(
        "AUTOMATION_HARD_DISABLED=false\nAPP_ENV=production\nRESEND_API_KEY=secret-two\n",
        encoding="utf-8",
    )

    first_values = fingerprints.parse_env_file(first)
    second_values = fingerprints.parse_env_file(second)

    assert fingerprints.configuration_fingerprint(first_values) == (
        fingerprints.configuration_fingerprint(second_values)
    )
    assert "RESEND_API_KEY" not in fingerprints.fingerprint_payload(first_values)["settings"]


def test_configuration_fingerprint_changes_with_release_behavior(tmp_path: Path) -> None:
    path = tmp_path / "staging.env"
    path.write_text("APP_ENV=production\nAUTOMATION_HARD_DISABLED=true\n", encoding="utf-8")
    before = fingerprints.configuration_fingerprint(fingerprints.parse_env_file(path))
    path.write_text("APP_ENV=production\nAUTOMATION_HARD_DISABLED=false\n", encoding="utf-8")
    after = fingerprints.configuration_fingerprint(fingerprints.parse_env_file(path))
    assert before != after


def test_configuration_fingerprint_rejects_duplicate_keys(tmp_path: Path) -> None:
    path = tmp_path / "staging.env"
    path.write_text("APP_ENV=production\nAPP_ENV=test\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate environment key"):
        fingerprints.parse_env_file(path)
