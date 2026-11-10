"""Purpose-specific encrypted registration envelopes; keys are never stored in SQL."""

import json

from cryptography.fernet import Fernet


def cipher(key):
    if not key:
        raise ValueError("Configure the registration encryption key.")
    return Fernet(key.encode())


def encrypt(key, values):
    return cipher(key).encrypt(json.dumps(values, ensure_ascii=False).encode()).decode()


def decrypt(key, value):
    return json.loads(cipher(key).decrypt(value.encode()))
