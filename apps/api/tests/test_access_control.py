from datetime import UTC, datetime

import pytest
from zhaoniu_api.access_control.codes import (
    CODE_ALPHABET,
    canonicalize_code,
    code_hmac,
    generate_code,
)
from zhaoniu_api.access_control.service import add_calendar_term


def test_access_codes_are_domain_separated_and_canonical() -> None:
    code = generate_code("INV")
    activation_code = generate_code("ACT")
    assert len(code) == 9
    assert code[4] == "-"
    assert set(code.replace("-", "")) <= set(CODE_ALPHABET)
    assert activation_code.startswith("ACT-")
    assert canonicalize_code(code.lower(), "INV") == canonicalize_code(code, "INV")
    assert code_hmac(code, "INV", "a" * 32) == code_hmac(code.replace("-", ""), "INV", "a" * 32)
    with pytest.raises(ValueError, match="invalid_code_format"):
        code_hmac(code, "ACT", "a" * 32)


def test_legacy_invitation_codes_remain_valid() -> None:
    legacy = "INV-ABCD-EFGH-JKLM-NPQR-STUV-WXYZ-23"

    assert canonicalize_code(legacy, "INV") == "INVABCDEFGHJKLMNPQRSTUVWXYZ23"
    assert code_hmac(legacy, "INV", "a" * 32) == code_hmac(
        legacy.replace("-", ""), "INV", "a" * 32
    )


def test_calendar_terms_clamp_month_end_and_leap_day() -> None:
    january_end = datetime(2027, 1, 31, 8, tzinfo=UTC)
    leap_day = datetime(2028, 2, 29, 8, tzinfo=UTC)
    assert add_calendar_term(january_end, "month") == datetime(2027, 2, 28, 8, tzinfo=UTC)
    assert add_calendar_term(leap_day, "year") == datetime(2029, 2, 28, 8, tzinfo=UTC)
