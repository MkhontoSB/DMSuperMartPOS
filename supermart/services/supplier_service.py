# supplier_service.py
import re

def validate_supplier(name, contact_person, phone, email, address):
    """
    Validates supplier information before it is stored in the database.

    Returns:
        None if all input is valid.
        An error message if validation fails.
    """

    # Remove unnecessary spaces from the beginning and end
    name = name.strip()
    contact_person = contact_person.strip()
    phone = phone.strip()
    email = email.strip()
    address = address.strip()

    # -----------------------------
    # Company Name Validation
    # -----------------------------

    if not name:
        return "Company name is required."

    if len(name) < 2:
        return "Company name must contain at least 2 characters."

    if len(name) > 100:
        return "Company name must not exceed 100 characters."

    # -----------------------------
    # Contact Person Validation
    # -----------------------------

    if not contact_person:
        return "Contact person is required."

    if len(contact_person) < 2:
        return "Contact person must contain at least 2 characters."

    if len(contact_person) > 100:
        return "Contact person must not exceed 100 characters."

    # Allows letters, spaces, apostrophes and hyphens
    if not re.fullmatch(r"[^\W\d_]+(?:[ '-][^\W\d_]+)*", contact_person):
        return "Contact person contains invalid characters."

    # -----------------------------
    # Phone Number Validation
    # -----------------------------

    if not phone:
        return "Phone number is required."

    # Remove spaces, brackets and hyphens for validation
    clean_phone = re.sub(r"[\s()-]", "", phone)

    # South African format:
    # 0821234567
    # +27821234567
    if not re.fullmatch(r"(?:\+27|0)[1-9][0-9]{8}", clean_phone):
        return "Enter a valid South African phone number."

    # -----------------------------
    # Email Validation
    # -----------------------------

    if not email:
        return "Email address is required."

    if len(email) > 254:
        return "Email address is too long."

    email_pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

    if not re.fullmatch(email_pattern, email):
        return "Enter a valid email address."

    # -----------------------------
    # Address Validation
    # -----------------------------

    if not address:
        return "Physical address is required."

    if len(address) < 5:
        return "Physical address is too short."

    if len(address) > 250:
        return "Physical address must not exceed 250 characters."

    # -----------------------------
    # Validation successful
    # -----------------------------

    return None
    