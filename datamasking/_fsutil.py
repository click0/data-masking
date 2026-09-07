#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Файлові утиліти без залежностей: атомарний запис приватних файлів.

Mapping-файли (plaintext чи .enc) містять ключ до відновлення
конфіденційних даних, тому:
  - створюються з правами 0600 (там, де ОС їх поважає);
  - пишуться у тимчасовий файл у тій самій директорії і підміняються
    через os.replace — на диску ніколи не лежить напівзаписаний mapping.
"""

import os
import tempfile
from pathlib import Path
from typing import Union

PRIVATE_MODE = 0o600


def atomic_write_private(path: Union[str, Path], data: bytes) -> Path:
    """Атомарно записує *data* у *path* з правами 0600.

    Повертає resolved Path. Тимчасовий файл створюється поруч
    (той самий каталог → той самий розділ → os.replace атомарний).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        try:
            os.fchmod(fd, PRIVATE_MODE)
        except (AttributeError, OSError):
            # Windows: fchmod відсутній / права не підтримуються
            pass
        with os.fdopen(fd, "wb") as fp:
            fp.write(data)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return path.resolve()
