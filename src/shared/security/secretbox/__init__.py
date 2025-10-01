# src/shared/security/secretbox/__init__.py
from .fernet_box import SecretBox

# singletons
_secret_box = SecretBox()

def get_encryptor():
    return _secret_box.encrypt

def get_decryptor():
    return _secret_box.decrypt
