import pytest

from apps.otp.services import PhoneError, normalize_phone


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+998 90 123-45-67", "998901234567"),
        ("998901234567", "998901234567"),
        ("901234567", "998901234567"),
        ("  998 (90) 123 4567 ", "998901234567"),
    ],
)
def test_normalize_phone_ok(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("bad", ["", "abc", "12345", "8999123456789", "00000000000"])
def test_normalize_phone_invalid(bad):
    with pytest.raises(PhoneError):
        normalize_phone(bad)
