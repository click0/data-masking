#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Власні шаблони маскування (masking_rules.custom_patterns, v3.0.29).

Запис — рядок-регулярний вираз або словник:

    custom_patterns:
      - "\\bТЕЛ-\\d{4}\\b"                    # маскувати збіг цілком
      - pattern: "посвідчення\\s+(\\d{6})"     # група 1 — що саме маскувати
        name: id_card                         # назва (для звіту/попереджень)
        action: mask                          # mask | skip | warn
      - pattern: "№\\s*\\d+-[IVXLC]+"          # номери законів
        action: skip                          # не чіпати взагалі

Дії (типова — router_rules.default_action, за замовчуванням mask):
  mask — детермінована маска тієї ж форми: цифра → цифра, велика літера →
         велика літера того ж алфавіту, решта (дефіси, пробіли) лишається;
         зберігається в mapping (категорія "custom"), unmask відновлює.
  skip — збіг захищається від УСЬОГО маскування (номери, дати, ПІБ, звання).
  warn — як skip, але з попередженням, скільки збігів лишилось відкритими.
"""
import random
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Pattern, Tuple

from datamasking.masking.helpers import get_deterministic_seed, add_to_mapping

ACTIONS = ("mask", "skip", "warn")
# Скільки збігів шаблонів з action: warn лишилось відкритими (CLI скидає
# перед запуском і друкує попередження після)
WARN_COUNTS: Dict[str, int] = {}
MAX_PATTERN_LENGTH = 1000

_UA_UPPER = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"
_UA_LOWER = _UA_UPPER.lower()
_LAT_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_LAT_LOWER = _LAT_UPPER.lower()


@dataclass(frozen=True)
class CustomPattern:
    name: str
    regex: Pattern[str]
    group: int
    action: str


def compile_patterns(raw: Any, default_action: str = "mask") -> Tuple[CustomPattern, ...]:
    """Перевіряє й компілює custom_patterns. Raises ValueError з текстом для користувача."""
    default_action = str(default_action or "mask").strip().lower()
    if default_action not in ACTIONS:
        raise ValueError(f"router_rules.default_action must be one of {', '.join(ACTIONS)}, "
                         f"got {default_action!r}")
    if raw in (None, "", []):
        return ()
    if not isinstance(raw, list):
        raise ValueError("masking_rules.custom_patterns must be a list")
    out: List[CustomPattern] = []
    for i, entry in enumerate(raw, 1):
        where = f"masking_rules.custom_patterns[{i}]"
        if isinstance(entry, str):
            entry = {"pattern": entry}
        if not isinstance(entry, dict):
            raise ValueError(f"{where} must be a string or a mapping with 'pattern'")
        pattern = entry.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            raise ValueError(f"{where}: 'pattern' must be a non-empty string")
        if len(pattern) > MAX_PATTERN_LENGTH:
            raise ValueError(f"{where}: pattern is longer than {MAX_PATTERN_LENGTH} characters")
        try:
            rx = re.compile(pattern)
        except re.error as e:
            raise ValueError(f"{where}: invalid regular expression: {e}") from None
        if rx.search("") is not None:
            raise ValueError(f"{where}: the pattern matches empty text")
        action = str(entry.get("action", default_action) or default_action).strip().lower()
        if action not in ACTIONS:
            raise ValueError(f"{where}: action must be one of {', '.join(ACTIONS)}, got {action!r}")
        name = str(entry.get("name") or f"custom{i}")
        unknown = set(entry) - {"pattern", "name", "action"}
        if unknown:
            raise ValueError(f"{where}: unknown key(s) {', '.join(sorted(unknown))}")
        out.append(CustomPattern(name=name, regex=rx, group=1 if rx.groups >= 1 else 0, action=action))
    return tuple(out)


ALWAYS_LAST = ("rank", "pib")


def build_processing_order(order: Any, overrides: Any, known: Tuple[str, ...]) -> Tuple[str, ...]:
    """router_rules.processing_order + priority_overrides → порядок фаз.

    Невказані типи додаються в типовому порядку; «rank» і «pib» дозволені,
    але завжди обробляються після шаблонних типів. priority_overrides:
    {тип: число} — менше число раніше; без перевизначення пріоритет =
    позиція у списку (0, 1, 2 …). Raises ValueError.
    """
    if order in (None, []):
        base = list(known)
    else:
        if not isinstance(order, list) or not all(isinstance(x, str) for x in order):
            raise ValueError("router_rules.processing_order must be a list of type names")
        unknown = [x for x in order if x not in known and x not in ALWAYS_LAST]
        if unknown:
            raise ValueError(f"router_rules.processing_order: unknown type(s) {', '.join(unknown)}; "
                             f"known: {', '.join(known + ALWAYS_LAST)}")
        base = []
        for x in order:
            if x in known and x not in base:
                base.append(x)
        base += [x for x in known if x not in base]
    overrides = overrides or {}
    if not isinstance(overrides, dict):
        raise ValueError("router_rules.priority_overrides must be a mapping {type: number}")
    for name, value in overrides.items():
        if name not in known and name not in ALWAYS_LAST:
            raise ValueError(f"router_rules.priority_overrides: unknown type {name!r}")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"router_rules.priority_overrides[{name}] must be a number, got {value!r}")
    ranked = sorted(enumerate(base), key=lambda iv: (overrides.get(iv[1], iv[0]), iv[0]))
    return tuple(name for _, name in ranked)


def iter_matches(cp: CustomPattern, text: str):
    """(start, end) того, що маскувати/захищати; порожні збіги пропускаються."""
    for m in cp.regex.finditer(text):
        if cp.group and m.group(cp.group) is not None:
            s, e = m.span(cp.group)
        else:
            s, e = m.span()
        if e > s:
            yield s, e


def _shape_mask(value: str, seed: int) -> str:
    rnd = random.Random(seed)
    out = []
    for ch in value:
        if ch.isdigit():
            out.append(str(rnd.randint(0, 9)))
        elif ch in _UA_UPPER:
            out.append(rnd.choice(_UA_UPPER))
        elif ch in _UA_LOWER:
            out.append(rnd.choice(_UA_LOWER))
        elif ch in _LAT_UPPER:
            out.append(rnd.choice(_LAT_UPPER))
        elif ch in _LAT_LOWER:
            out.append(rnd.choice(_LAT_LOWER))
        else:
            out.append(ch)
    return "".join(out)


def mask_custom(original: str, masking_dict: Dict, instance_counters: Dict,
                document: str = "") -> str:
    """Детермінована маска тієї ж форми; ≠ оригіналу, не збігається з
    іншими масками цієї категорії і не трапляється в тексті документа
    (інакше unmask був би неоднозначним)."""
    category = masking_dict["mappings"].setdefault("custom", {})
    existing = category.get(original)
    if isinstance(existing, dict):
        return add_to_mapping(masking_dict, instance_counters, "custom", original, existing["masked_as"])
    taken = {info["masked_as"] for info in category.values() if isinstance(info, dict)} | set(category)
    base = get_deterministic_seed(original)
    masked: Optional[str] = None
    for attempt in range(50):
        candidate = _shape_mask(original, base if attempt == 0 else get_deterministic_seed(f"{original}\x00{attempt}"))
        if candidate != original and candidate not in taken and candidate not in document:
            masked = candidate
            break
    if masked is None:  # без цифр і літер (лише розділювачі) — маскувати нічого
        return original
    return add_to_mapping(masking_dict, instance_counters, "custom", original, masked)
