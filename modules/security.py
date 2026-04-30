#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Security Module v2.5.1

Provides AES-256-GCM encryption/decryption of mapping files
for data_masking.py.

File format: [16 bytes salt][12 bytes nonce][encrypted data with 16 bytes tag]

Author: Vladyslav V. Prodan
Contact: github.com/click0
License: BSD 3-Clause
Year: 2025-2026
"""

__version__ = "2.5.1"

import json
import os
import getpass
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

CRYPTOGRAPHY_AVAILABLE = False
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    logger.debug("cryptography package not available; encryption disabled")


class MappingSecurityManager:
    """Manages encryption and decryption of mapping files.

    Uses AES-256-GCM authenticated encryption with PBKDF2-derived keys.
    File layout: [16 bytes salt][12 bytes nonce][ciphertext + 16 bytes GCM tag]
    """

    SALT_LENGTH: int = 16
    NONCE_LENGTH: int = 12
    KEY_LENGTH: int = 32
    ITERATIONS: int = 600_000

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        """Derive a 256-bit key from *password* and *salt* via PBKDF2-HMAC-SHA256.

        Args:
            password: User-supplied password string.
            salt: Random salt bytes (``SALT_LENGTH`` long).

        Returns:
            Raw 32-byte key suitable for AES-256.
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError(
                "The 'cryptography' package is required for encryption. "
                "Install it with: pip install cryptography"
            )
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=MappingSecurityManager.KEY_LENGTH,
            salt=salt,
            iterations=MappingSecurityManager.ITERATIONS,
        )
        return kdf.derive(password.encode("utf-8"))

    # ------------------------------------------------------------------
    # Core encrypt / decrypt
    # ------------------------------------------------------------------

    def encrypt_mapping(
        self,
        mapping_dict: Dict[str, Any],
        password: str,
        output_path: Any,
    ) -> Path:
        """Encrypt *mapping_dict* with AES-256-GCM and write to *output_path*.

        Returns the resolved Path of the written file.
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError(
                "The 'cryptography' package is required for encryption. "
                "Install it with: pip install cryptography"
            )

        output_path = Path(output_path)

        json_bytes = json.dumps(
            mapping_dict, ensure_ascii=False, indent=2
        ).encode("utf-8")

        salt = os.urandom(self.SALT_LENGTH)
        nonce = os.urandom(self.NONCE_LENGTH)
        key = self._derive_key(password, salt)

        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, json_bytes, None)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as fp:
            fp.write(salt)
            fp.write(nonce)
            fp.write(ciphertext)

        logger.info("Encrypted mapping written to %s", output_path)
        return output_path.resolve()

    def decrypt_mapping(
        self,
        encrypted_path: Any,
        password: str,
    ) -> Dict[str, Any]:
        """Read an AES-256-GCM encrypted mapping file and return the dict.

        Raises ValueError if the file is too short or the password is wrong.
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError(
                "The 'cryptography' package is required for decryption. "
                "Install it with: pip install cryptography"
            )

        encrypted_path = Path(encrypted_path)
        raw = encrypted_path.read_bytes()

        min_length = self.SALT_LENGTH + self.NONCE_LENGTH + 16  # tag
        if len(raw) < min_length:
            raise ValueError(
                f"Encrypted file is too short ({len(raw)} bytes); "
                f"expected at least {min_length} bytes."
            )

        salt = raw[: self.SALT_LENGTH]
        nonce = raw[self.SALT_LENGTH : self.SALT_LENGTH + self.NONCE_LENGTH]
        ciphertext = raw[self.SALT_LENGTH + self.NONCE_LENGTH :]

        key = self._derive_key(password, salt)
        aesgcm = AESGCM(key)

        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        except Exception as exc:
            raise ValueError(
                "Decryption failed. Wrong password or corrupted file."
            ) from exc

        return json.loads(plaintext.decode("utf-8"))

    # ------------------------------------------------------------------
    # Universal load / save helpers
    # ------------------------------------------------------------------

    def load_mapping(
        self,
        path: Any,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Load a mapping from *path*, auto-detecting format.

        .json files are loaded directly; .enc files are decrypted
        with the supplied *password*.

        Raises ValueError for unsupported extensions or missing password.
        """
        path = Path(path)

        if path.suffix == ".json":
            with open(path, "r", encoding="utf-8") as fp:
                return json.load(fp)

        if path.suffix == ".enc":
            if not password:
                raise ValueError(
                    "A password is required to load an encrypted mapping file."
                )
            return self.decrypt_mapping(path, password)

        raise ValueError(
            f"Unsupported mapping file extension: {path.suffix!r}. "
            "Use '.json' or '.enc'."
        )

    def save_mapping(
        self,
        mapping_dict: Dict[str, Any],
        path: Any,
        password: Optional[str] = None,
        encrypt: bool = False,
    ) -> Path:
        """Save *mapping_dict* to *path*, optionally encrypting.

        Returns the resolved Path of the written file.
        """
        path = Path(path)

        if encrypt:
            if not password:
                raise ValueError(
                    "A password is required to save an encrypted mapping file."
                )
            return self.encrypt_mapping(mapping_dict, password, path)

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(mapping_dict, fp, ensure_ascii=False, indent=2)

        logger.info("Mapping written to %s", path)
        return path.resolve()


# ----------------------------------------------------------------------
# Convenience functions
# ----------------------------------------------------------------------

def get_password(confirm: bool = False) -> str:
    """Prompt the user for a password via getpass.

    When *confirm* is True, asks twice and verifies match.
    """
    password = getpass.getpass("Enter mapping password: ")
    if confirm:
        password2 = getpass.getpass("Confirm mapping password: ")
        if password != password2:
            raise ValueError("Passwords do not match.")
    return password


def get_password_from_env(env_var: str = "DATA_MASKING_PASSWORD") -> Optional[str]:
    """Return a password from the environment variable *env_var*.

    Args:
        env_var: Name of the environment variable to read.
    Returns:
        The password string, or ``None`` if the variable is not set.
    """
    return os.environ.get(env_var)


def is_encryption_available() -> bool:
    """Return True if the cryptography library is importable."""
    return CRYPTOGRAPHY_AVAILABLE
