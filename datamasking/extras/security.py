#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Security Module v2.6.0

Provides AES-256-GCM encryption/decryption of mapping files
for data_masking.py.

File format: [16 bytes salt][12 bytes nonce][encrypted data with 16 bytes tag]

Author: Vladyslav V. Prodan
Contact: github.com/click0
License: BSD 3-Clause
Year: 2025-2026
"""

from datamasking._version import __version__  # єдине джерело версії

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
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    from cryptography.hazmat.primitives import hashes
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    logger.debug("cryptography package not available; encryption disabled")


class MappingSecurityManager:
    """Manages encryption and decryption of mapping files.

    Uses AES-256-GCM authenticated encryption.

    Формат 1 (за замовчуванням, читають усі версії 2.3+):
        [16 bytes salt][12 bytes nonce][ciphertext + 16 bytes GCM tag],
        ключ — PBKDF2-HMAC-SHA256, 600 000 ітерацій.
    Формат 2 (v3.0.29+, якщо security.key_derivation: scrypt або інша
    довжина солі; старі версії його НЕ прочитають):
        b"DMENC2" [2 bytes: довжина заголовка][JSON-заголовок: kdf і параметри]
        [salt][12 bytes nonce][ciphertext + tag]; заголовок автентифікується
        як associated data GCM — підмінити параметри непомітно не можна.
    Читання розпізнає формат сам.
    """

    MAGIC_V2: bytes = b"DMENC2"
    # Межі параметрів scrypt (захист від заголовка, що вимагає гігабайти пам'яті)
    SCRYPT_MAX_MEMORY: int = 1 << 30

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

    @staticmethod
    def check_kdf(kdf: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Нормалізує і перевіряє параметри виведення ключа.

        kdf: {"kdf": "pbkdf2"|"scrypt", "n", "r", "p", "salt_length"}.
        Raises ValueError з текстом для користувача.
        """
        kdf = dict(kdf or {})
        name = str(kdf.get("kdf", "pbkdf2") or "pbkdf2").strip().lower()
        if name not in ("pbkdf2", "scrypt"):
            raise ValueError(f"security.key_derivation must be pbkdf2 or scrypt, got {name!r}")

        names = {"n": "scrypt_n", "r": "scrypt_r", "p": "scrypt_p", "salt_length": "salt_length"}

        def as_int(key: str, default: int, lo: int, hi: int) -> int:
            value = kdf.get(key, default)
            if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
                raise ValueError(f"security.{names[key]} must be an integer between {lo} and {hi}, "
                                 f"got {value!r}")
            return value

        salt_key = "salt_length"
        out: Dict[str, Any] = {"kdf": name, "salt_length": as_int(salt_key, 16, 16, 64)}
        if name == "scrypt":
            out["n"] = as_int("n", 16384, 2, 1 << 20)
            if out["n"] & (out["n"] - 1):
                raise ValueError(f"security.scrypt_n must be a power of two, got {out['n']}")
            out["r"] = as_int("r", 8, 1, 64)
            out["p"] = as_int("p", 1, 1, 16)
            if 128 * out["n"] * out["r"] > MappingSecurityManager.SCRYPT_MAX_MEMORY:
                raise ValueError("security.scrypt_n × scrypt_r needs more than 1 GiB of memory")
        return out

    @classmethod
    def _derive_key_v2(cls, password: str, salt: bytes, header: Dict[str, Any]) -> bytes:
        if header.get("kdf") == "scrypt":
            kdf = Scrypt(salt=salt, length=cls.KEY_LENGTH, n=int(header["n"]),
                         r=int(header["r"]), p=int(header["p"]))
            return kdf.derive(password.encode("utf-8"))
        if header.get("kdf") == "pbkdf2":
            iterations = int(header.get("iterations", cls.ITERATIONS))
            if not 100_000 <= iterations <= 10_000_000:
                raise ValueError("Encrypted file header has an invalid PBKDF2 iteration count")
            return PBKDF2HMAC(algorithm=hashes.SHA256(), length=cls.KEY_LENGTH,
                              salt=salt, iterations=iterations).derive(password.encode("utf-8"))
        raise ValueError(f"Encrypted file uses an unknown key derivation: {header.get('kdf')!r}")

    # ------------------------------------------------------------------
    # Core encrypt / decrypt
    # ------------------------------------------------------------------

    def encrypt_mapping(
        self,
        mapping_dict: Dict[str, Any],
        password: str,
        output_path: Any,
        kdf: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Encrypt *mapping_dict* with AES-256-GCM and write to *output_path*.

        kdf — параметри виведення ключа (див. check_kdf). PBKDF2 із сіллю
        16 байт (за замовчуванням) — формат 1, сумісний зі старими версіями;
        інакше — формат 2 із заголовком.

        Returns the resolved Path of the written file.
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError(
                "The 'cryptography' package is required for encryption. "
                "Install it with: pip install cryptography"
            )

        if not password:
            raise ValueError("A non-empty password is required to encrypt a mapping file.")
        output_path = Path(output_path)

        json_bytes = json.dumps(
            mapping_dict, ensure_ascii=False, indent=2
        ).encode("utf-8")

        params = self.check_kdf(kdf)
        from datamasking._fsutil import atomic_write_private
        nonce = os.urandom(self.NONCE_LENGTH)

        if params["kdf"] == "pbkdf2" and params["salt_length"] == self.SALT_LENGTH:
            salt = os.urandom(self.SALT_LENGTH)
            key = self._derive_key(password, salt)
            ciphertext = AESGCM(key).encrypt(nonce, json_bytes, None)
            # Атомарно і з правами 0600 — це ключ до оригіналів
            resolved = atomic_write_private(output_path, salt + nonce + ciphertext)
        else:
            header: Dict[str, Any] = {"v": 2, "kdf": params["kdf"], "salt_length": params["salt_length"]}
            if params["kdf"] == "scrypt":
                header.update(n=params["n"], r=params["r"], p=params["p"])
            else:
                header["iterations"] = self.ITERATIONS
            header_bytes = json.dumps(header, sort_keys=True).encode("ascii")
            prefix = self.MAGIC_V2 + len(header_bytes).to_bytes(2, "big") + header_bytes
            salt = os.urandom(params["salt_length"])
            key = self._derive_key_v2(password, salt, header)
            ciphertext = AESGCM(key).encrypt(nonce, json_bytes, prefix)
            resolved = atomic_write_private(output_path, prefix + salt + nonce + ciphertext)

        logger.info("Encrypted mapping written to %s", resolved)
        return resolved

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

        if raw.startswith(self.MAGIC_V2):
            return self._decrypt_v2(raw, password)

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

        data = json.loads(plaintext.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Decrypted mapping is not a JSON object")
        return data

    def _decrypt_v2(self, raw: bytes, password: str) -> Dict[str, Any]:
        """Формат 2: заголовок із параметрами KDF, автентифікований GCM."""
        try:
            pos = len(self.MAGIC_V2)
            header_len = int.from_bytes(raw[pos:pos + 2], "big")
            header_bytes = raw[pos + 2:pos + 2 + header_len]
            header = json.loads(header_bytes.decode("ascii"))
            if not isinstance(header, dict) or header.get("v") != 2:
                raise ValueError("bad header")
            params = self.check_kdf({"kdf": header.get("kdf"), "n": header.get("n", 16384),
                                     "r": header.get("r", 8), "p": header.get("p", 1),
                                     "salt_length": header.get("salt_length", 16)})
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError(f"Encrypted file has an invalid header: {exc}") from exc
        prefix_end = pos + 2 + header_len
        salt_end = prefix_end + params["salt_length"]
        nonce_end = salt_end + self.NONCE_LENGTH
        if len(raw) < nonce_end + 16:
            raise ValueError("Encrypted file is too short.")
        key = self._derive_key_v2(password, raw[prefix_end:salt_end], header)
        try:
            plaintext = AESGCM(key).decrypt(raw[salt_end:nonce_end], raw[nonce_end:], raw[:prefix_end])
        except Exception as exc:
            raise ValueError("Decryption failed. Wrong password or corrupted file.") from exc
        data = json.loads(plaintext.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Decrypted mapping is not a JSON object")
        return data

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
                data = json.load(fp)
            if not isinstance(data, dict):
                raise ValueError("Mapping file is not a JSON object")
            return data

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
        return Path(path).resolve()


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
