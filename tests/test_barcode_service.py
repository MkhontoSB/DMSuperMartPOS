
import pytest

from supermart.services.barcode_service import ean13_checksum


def test_ean13_checksum_known_example():
    assert ean13_checksum("400638133393") == "4006381333931"


def test_ean13_checksum_preserves_leading_zeros():
    assert ean13_checksum("012345678901") == "0123456789012"


def test_ean13_checksum_returns_13_digits():
    result = ean13_checksum("400638133393")

    assert len(result) == 13
    assert result.isdigit()


@pytest.mark.parametrize(
    "invalid_code",
    [
        "",
        "12345678901",
        "1234567890123",
        "12345ABC9012",
        "12345678901 ",
        "１２３４５６７８９０１２",
    ],
)
def test_ean13_checksum_rejects_invalid_input(invalid_code):
    with pytest.raises(ValueError):
        ean13_checksum(invalid_code)


def test_ean13_checksum_rejects_integer_input():
    with pytest.raises(ValueError):
        ean13_checksum(400638133393)
