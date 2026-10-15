
import pytest

from supermart.services.supplier_service import validate_supplier


VALID_SUPPLIER = {
    "name": "ABC Supplies",
    "contact_person": "John Smith",
    "phone": "0821234567",
    "email": "john@example.co.za",
    "address": "123 Main Street",
}


def validate(**overrides):
    data = {**VALID_SUPPLIER, **overrides}

    return validate_supplier(
        data["name"],
        data["contact_person"],
        data["phone"],
        data["email"],
        data["address"],
    )


def test_valid_supplier_is_accepted():
    assert validate() is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("name", "A"),
        ("name", "A" * 101),
        ("contact_person", ""),
        ("contact_person", "J"),
        ("contact_person", "John123"),
        ("contact_person", "John_Smith"),
        ("phone", ""),
        ("phone", "12345"),
        ("phone", "082123456"),
        ("phone", "08212345678"),
        ("email", ""),
        ("email", "not-an-email"),
        ("email", "john@invalid"),
        ("address", ""),
        ("address", "123"),
        ("address", "A" * 251),
    ],
)
def test_invalid_supplier_fields_are_rejected(field, value):
    assert validate(**{field: value}) is not None


@pytest.mark.parametrize(
    "phone",
    [
        "0821234567",
        "+27821234567",
        "082 123 4567",
        "082-123-4567",
        "(082) 123-4567",
    ],
)
def test_valid_south_african_phone_formats_are_accepted(phone):
    assert validate(phone=phone) is None


def test_supplier_input_with_surrounding_whitespace_is_accepted():
    assert validate(
        name="  ABC Supplies  ",
        contact_person="  John Smith  ",
        phone="  0821234567  ",
        email="  john@example.co.za  ",
        address="  123 Main Street  ",
    ) is None


def test_unicode_contact_name_is_accepted():
    assert validate(contact_person="José Dlamini") is None
