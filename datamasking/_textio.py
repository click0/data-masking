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
# UTF-32 — перед UTF-16: BOM UTF-32-LE починається з BOM UTF-16-LE
_BOMS = ((codecs.BOM_UTF32_LE, "utf-32-le"), (codecs.BOM_UTF32_BE, "utf-32-be"),
         (codecs.BOM_UTF16_LE, "utf-16-le"), (codecs.BOM_UTF16_BE, "utf-16-be"))
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
    if allowed is not None and not isinstance(allowed, (list, tuple)):
        raise ValueError("validation.allowed_encodings must be a list of encodings")
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
    if encoding == "auto":
        # BOM однозначно називає кодування. До 3.1.21 UTF-16 «декодувався»
        # як cp1251 (однобайтові кодування приймають будь-які байти), і
        # документ виходив незамаскованим з кодом 0. Кодек із явним порядком
        # байтів лишає BOM у тексті символом U+FEFF — і вихід пишеться так само
        for bom, enc in _BOMS:
            if raw.startswith(bom):
                return raw.decode(enc), enc
    candidates = list(allowed) if encoding == "auto" else [encoding]
    last_error: Exception = UnicodeDecodeError(DEFAULT_ENCODING, b"", 0, 1, "no encodings to try")
    for enc in candidates:
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError as e:
            last_error = e
            continue
        if encoding == "auto" and "\x00" in text:
            # Символи NUL у «тексті» — це UTF-16/32 без BOM, а не cp1251
            pos = text.index("\x00")
            last_error = UnicodeDecodeError(enc, raw, pos, pos + 1,
                                            "NUL character (UTF-16 or UTF-32 without a BOM?)")
            continue
        return text, normalize_encoding(enc)
    if encoding == "auto":
        raise UnicodeDecodeError(
            getattr(last_error, "encoding", "auto"), raw, 0, 1,
            f"none of the allowed encodings ({', '.join(candidates)}) could decode the file "
            f"({getattr(last_error, 'reason', last_error)})")
    raise last_error
