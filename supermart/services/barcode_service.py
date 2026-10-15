# barcode_service.py

def ean13_checksum(code_str: str) -> str:
    """
    Generate an EAN-13 barcode from exactly 12 numeric digits.

    Raises:
        ValueError: If the input is not exactly 12 digits.
    """
    if not isinstance(code_str, str) or len(code_str) != 12:
        raise ValueError("EAN-13 input must contain exactly 12 digits.")

    if not code_str.isascii() or not code_str.isdigit():
        raise ValueError("EAN-13 input must contain only numeric digits.")

    digits = [int(digit) for digit in code_str]

    checksum = (
        10 - (
            sum(digits[::2]) +
            sum(digits[1::2]) * 3
        ) % 10
    ) % 10

    return code_str + str(checksum)
