#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Рядкові значення JSON як один текст (v3.1.21).

Номери входжень масок (instance tracking) при маскуванні JSON спільні для
всього документа, а unmask до 3.1.21 обробляв кожен рядок окремо, з
лічильниками від нуля: якщо два різні оригінали в різних рядках діставали
одну маску («№ 2» і «№ 6» → «№ 4»), другий відновлювався першим. Перевірка
колізій маски з відкритим текстом теж бачила лише свій рядок. Тому і mask,
і unmask обробляють усі рядки разом — через роздільник, якого немає в
жодному з них (окремий рядок із символу приватної зони Unicode: не літера,
не цифра, не пробіл, тож жоден шаблон його не перетинає).

Ключі словників не маскуються й сюди не входять. Лише stdlib — модуль
імпортують і mask, і unmask.
"""
from typing import Any, Iterator, List, Optional


def collect_strings(data: Any) -> List[str]:
    """Рядкові значення (не ключі) у порядку обходу dict/list."""
    out: List[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str):
            out.append(node)

    walk(data)
    return out


def replace_strings(data: Any, values: Iterator[str]) -> Any:
    """Копія *data*, де рядкові значення по черзі замінено на *values*."""
    if isinstance(data, dict):
        return {key: replace_strings(value, values) for key, value in data.items()}
    if isinstance(data, list):
        return [replace_strings(item, values) for item in data]
    if isinstance(data, str):
        return next(values)
    return data


def separator(strings: List[str]) -> Optional[str]:
    """Роздільник, якого немає в жодному рядку (None — якщо всі символи
    приватної зони вже зайняті)."""
    for code in range(0xE000, 0xF900):
        ch = chr(code)
        if not any(ch in s for s in strings):
            return "\n" + ch + "\n"
    return None
