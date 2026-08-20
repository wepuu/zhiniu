from datetime import UTC, datetime

import pytest
from zhaoniu_api.access_control.codes import canonicalize_code, code_hmac, generate_code
from zhaoniu_api.access_control.service import add_calendar_term


def test_access_codes_are_domain_separated_and_canonical() -> None:
    code = generate_code("INV")
    assert code.startswith("INV-")
    assert canonicalize_code(code.lower(), "INV") == canonicalize_code(code, "INV")
    assert code_hmac(code, "INV", "a" * 32) == code_hmac(code.replace("-", ""), "INV", "a" * 32)
    with pytest.raises(ValueError, match="invalid_code_format"):
        code_hmac(code, "ACT", "a" * 32)


def test_calendar_terms_clamp_month_end_and_leap_day() -> None:
    january_end = datetime(2027, 1, 31, 8, tzinfo=UTC)
    leap_day = datetime(2028, 2, 29, 8, tzinfo=UTC)
    assert add_calendar_term(january_end, "month") == datetime(2027, 2, 28, 8, tzinfo=UTC)
    assert add_calendar_term(leap_day, "year") == datetime(2029, 2, 28, 8, tzinfo=UTC)
