# src/identity/domain/value_objects/__init__.py
"""Value objects for the identity domain."""

from .email import Email
from .phone import PhoneNumber
from .role import Role
from .slug import Slug
from .password_hash import PasswordHash
from .name import Name
from .timestamps import Timestamps

__all__ = [
    'Email',
    'PhoneNumber', 
    'Role',
    'Slug',
    'PasswordHash',
    'Name',
    'Timestamps',
]