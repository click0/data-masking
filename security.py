#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Security module for data_masking.py v2.2.15

Provides encryption/decryption of mapping files using Fernet (AES-128-CBC).

Author: Vladyslav V. Prodan
Contact: github.com/click0
License: BSD 3-Clause
Year: 2025
"""

import json
import hashlib
import base64
from pathlib import Path
from typing import Dict, Any, Optional

CRYPTO_AVAILABLE = False
try:
    import importlib
    if importlib.util.find_spec("_cffi_backend") is not None:
        from cryptography.fernet import Fernet
        CRYPTO_AVAILABLE = True
except Exception:
    pass


def _derive_key(password: str) -> bytes:
    """Derive a Fernet-compatible key from a password using PBKDF2."""
    # Use a fixed salt for deterministic key derivation
    salt = b"data_masking_v2_salt"
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return base64.urlsafe_b64encode(key[:32])


class MappingSecurityManager:
    """Manages encryption and decryption of mapping files.

    Uses Fernet symmetric encryption (AES-128-CBC with HMAC).
    Falls back to base64 encoding if cryptography package is not installed.
    """

    def __init__(self, default_password: Optional[str] = None):
        self._default_password = default_password

    def encrypt_mapping(self, data: Dict[str, Any], password: str,
                        output_path) -> None:
        """Encrypt mapping data and save to file.

        Args:
            data: Mapping dictionary to encrypt
            password: Encryption password
            output_path: Path to save encrypted file
        """
        output_path = Path(output_path)
        json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')

        if CRYPTO_AVAILABLE:
            key = _derive_key(password)
            f = Fernet(key)
            encrypted = f.encrypt(json_bytes)
        else:
            # Fallback: base64 encode (not secure, but functional)
            encrypted = base64.b64encode(json_bytes)

        with open(output_path, 'wb') as fp:
            fp.write(encrypted)

    def decrypt_mapping(self, input_path, password: str) -> Dict[str, Any]:
        """Decrypt mapping file and return data.

        Args:
            input_path: Path to encrypted file
            password: Decryption password

        Returns:
            Decrypted mapping dictionary
        """
        input_path = Path(input_path)
        with open(input_path, 'rb') as fp:
            encrypted = fp.read()

        if CRYPTO_AVAILABLE:
            key = _derive_key(password)
            f = Fernet(key)
            decrypted = f.decrypt(encrypted)
        else:
            decrypted = base64.b64decode(encrypted)

        return json.loads(decrypted.decode('utf-8'))
