# roles.py

from enum import StrEnum

class Role(StrEnum):
    SYSTEM_ADMIN = "system_admin"
    STORE_OWNER = "store_owner"
    SUPPLIER = "supplier"

ALLOWED_ROLE_VALUES = {role.value for role in Role}