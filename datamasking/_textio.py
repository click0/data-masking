#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Читання вхідних файлів у заданому або визначеному кодуванні (v3.0.28).

system.encoding: "utf-8" (як було завжди), будь-яке інше кодування Python
(cp1251 …) або "auto" — по черзі пробуються validation.allowed_encodings,
береться перше, яке декодує файл без помилок. Документи з Windows часто
в cp1251; до 3.0.28 такий файл відхилявся з UnicodeDecodeError.

Лише stdlib — модуль імпортують і mask, і unmask.
"""
import codecs
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

DEFAULT_ENCODING = "utf-8"
DEFAULT_ALLOWED = ("utf-8", "cp1251", "latin-1")


def normalize_encoding(name: str) -> str:
    """Канонічна назва кодування Python ('CP1251' → 'cp1251'); ValueError, якщо невідоме."""
    try:
        return codecs.lookup(str(name).strip()).name
    except LookupError:
        raise ValueError(f"unknown encoding: {name!r}") from None


def check_encoding_settings(encoding: str, allowed: Optional[Iterable[str]]) -> Tuple[str, List[str]]:
    """Перевіряє system.encoding / validation.allowed_encodings.

    Returns:
        (encoding — "auto" або канонічна назва, канонічний список дозволених)
    Raises:
        ValueError з текстом для користувача.
    """
    allowed_list = [normalize_encoding(a) for a in (DEFAULT_ALLOWED if allowed is None else allowed)]
    if not allowed_list:
        raise ValueError("validation.allowed_encodings must not be empty")
    enc = str(encoding or DEFAULT_ENCODING).strip()
    if enc.lower() == "auto":
        return "auto", allowed_list
    canonical = normalize_encoding(enc)
    if canonical not in allowed_list:
        raise ValueError(f"system.encoding {enc!r} is not in validation.allowed_encodings "
                         f"({', '.join(allowed_list)})")
    return canonical, allowed_list


def read_text(path: Path, encoding: str = DEFAULT_ENCODING,
              allowed: Iterable[str] = DEFAULT_ALLOWED) -> Tuple[str, str]:
    """Читає файл як текст. Повертає (текст, використане кодування).

    Переноси рядків не перетворюються (як open(..., newline='')).
    """
    raw = Path(path).read_bytes()
    candidates = list(allowed) if encoding == "auto" else [encoding]
    last_error: Exception = UnicodeDecodeError(DEFAULT_ENCODING, b"", 0, 1, "no encodings to try")
    for enc in candidates:
        try:
            return raw.decode(enc), normalize_encoding(enc)
        except UnicodeDecodeError as e:
            last_error = e
    if encoding == "auto":
        raise UnicodeDecodeError(
            getattr(last_error, "encoding", "auto"), raw, 0, 1,
            f"none of the allowed encodings ({', '.join(candidates)}) could decode the file")
    raise last_error
