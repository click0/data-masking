#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Виключення маскування: вбудовані переліки і їх доповнення з конфігурації.

Вбудовані переліки (раніше — у masking/constants.py):
  BUILTIN_ABBREVIATIONS — абревіатури, які не маскуються як прізвища;
  BUILTIN_WORDS         — слова, які не є частиною ПІБ;
  BUILTIN_LEGAL_ACTS    — назви нормативних актів: дата після «… від» не
                          зсувається («Закону України від 06.12.1991»).

Повні переліки лежать у ``config.yaml`` (секція ``dictionaries``, v3.1.3):
``abbreviations``, ``non_name_words``, ``legal_acts``. Тут — їх запасна
копія: вона діє, коли ключа немає (або він null), напр. без PyYAML чи з
іншим файлом конфігурації. Тест звіряє її з config.yaml.

Секція конфігурації ``exclusions`` (v3.1.1) їх доповнює:

    exclusions:
      abbreviations: [ОК, ТРО]              # не маскувати як прізвище
      words: [Рада, Раді]                   # не вважати частиною ПІБ
      phrases: ["Верховн* Рад*"]            # не чіпати взагалі (як custom skip)
      legal_acts: ["розпорядженн* президента"]  # назва не маскується, дата
                                                # після «… від» не зсувається
      always_mask: ["Сокіл", "позивний Грім"]   # маскувати завжди (як custom mask)
      remove: [Положення]                   # прибрати вбудоване слово/абревіатуру/акт

Слово з ``*`` у кінці — основа з будь-яким закінченням (``Кабінет*`` =
Кабінет, Кабінету, Кабінетом …); слова фрази розділяються будь-якими
пробілами; регістр не враховується. Без цієї секції поведінка (і маски)
такі самі, як до 3.1.1.
"""
import re
from dataclasses import dataclass
from typing import Any, FrozenSet, Iterable, List, Pattern, Tuple

BUILTIN_ABBREVIATIONS: Tuple[str, ...] = (
    "зсу", "моу", "всу", "дпсу", "нгу", "дснс", "сбу", "гур", "тцк", "сп", "кму", "отцксп",
)

BUILTIN_WORDS: Tuple[str, ...] = (
    "Дійсним", "дійсним", "Відповідно", "відповідно", "Згідно", "згідно",
    "Відповідальний", "відповідальний", "Командир", "командир", "командира",
    "Начальник", "начальник", "Заступник", "заступник",
    "Виконуючий", "виконуючий", "обов'язки", "обав'язки",
    "доповідаю", "прошу", "наказую", "призначити", "звільнити",
    "проявив", "виконав", "оголосити", "оголосити",
    "про", "по", "від", "до", "за", "суті", "мною", "Вас", "вас",
    "Вам", "вам", "Вами", "вами", "Ваш", "ваш", "Ваша", "ваша", "Ваше", "ваше",
    "Повідомляємо", "повідомляємо", "Просимо", "просимо",
    "Направляємо", "направляємо", "Надаємо", "надаємо",
    "зв'язку", "порушення", "вимог",
    "Збройних", "збройних", "України", "україни", "служби", "Служби",
    "військової", "Військової", "частини", "Частини", "взводу", "Взводу",
    "батальйону", "Батальйону", "роти", "Роти",
    "Статуту", "статуту", "Указу", "указу", "Закону", "закону",
    "Кодексу", "кодексу", "Положення", "положення",
    "Інструкції", "інструкції", "наказу", "Наказу", "наказом", "Наказом",
    "рапорту", "Рапорту", "статей", "Статей", "пункту", "Пункту",
    "неналежііе", "инутрішньої", "радіовіzUділення",
    "с~гатуту", "року", "Року", "числа", "місяця",
    "один", "два", "три", "чотири", "п'ять",
    # Службові маркери-мітки (щоб не плутались із самим ПІБ у форматах
    # "ПІБ: Петренко..." чи логах "ПІБ «138» → «Міронов...»")
    "ПІБ", "піб", "Піб", "звання", "Звання", "ЗВАННЯ",
    "ІПН", "іпн", "Іпн", "РНОКПП", "паспорт", "Паспорт",
    # «Кабінет Міністрів» у всіх відмінках — не ПІБ («постанови Кабінету
    # Міністрів» маскувалось як «Кабалу Михайло»). Змінюється лише перше
    # слово: Кабінет / Кабінету / Кабінетом / Кабінеті / Кабінете + Міністрів
    "Кабінет", "Кабінету", "Кабінетові", "Кабінетом", "Кабінеті", "Кабінете",
    "Міністрів",)

BUILTIN_LEGAL_ACTS: Tuple[str, ...] = (
    "закон*",
    "кодекс*",
    "конституці*",
    "указ* президента",
    "постанов* кабінету міністрів",
    "постанов* верховної ради",
    "постанов* кму",
    "постанов* кмy",  # латинська y — так трапляється в документах
)

KEYS = ("abbreviations", "words", "phrases", "legal_acts", "always_mask", "remove")
_MAX_ITEMS = 10_000
_MAX_LENGTH = 200
_WORD_EDGE_BEFORE = r"(?<![\w'’ʼ])"
_WORD_EDGE_AFTER = r"(?![\w'’ʼ])"


def phrase_regex(phrase: str) -> str:
    """«Кабінет* Міністрів» → ``Кабінет\\w*\\s+Міністрів`` (без меж слова)."""
    parts = []
    for word in phrase.split():
        if word.endswith("*"):
            parts.append(re.escape(word[:-1]) + r"\w*")
        else:
            parts.append(re.escape(word))
    return r"\s+".join(parts)


def legal_act_regex(acts: Iterable[str]) -> Pattern[str]:
    """Дата одразу після «<акт> … від» (у межах речення, до 80 символів)."""
    alternatives = "|".join(phrase_regex(a) for a in acts)
    return re.compile(r"(?:" + alternatives + r")[^\n.;]{0,80}?\bвід\s*$", re.IGNORECASE)


DICTIONARY_KEYS = ("abbreviations", "non_name_words", "legal_acts")


def _items(section: Any, key: str, where_section: str = "exclusions") -> List[str]:
    value = getattr(section, key, None) if not isinstance(section, dict) else section.get(key)
    where = f"{where_section}.{key}"
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{where} must be a list of strings")
    if len(value) > _MAX_ITEMS:
        raise ValueError(f"{where}: more than {_MAX_ITEMS} entries")
    out = []
    for i, item in enumerate(value, 1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{where}[{i}] must be a non-empty string")
        item = " ".join(item.split())
        if len(item) > _MAX_LENGTH:
            raise ValueError(f"{where}[{i}] is longer than {_MAX_LENGTH} characters")
        for word in item.split():
            stem = word[:-1] if word.endswith("*") else word
            if "*" in stem:
                raise ValueError(f"{where}[{i}]: '*' is allowed only at the end of a word")
            if len(stem) < 2:
                raise ValueError(f"{where}[{i}]: word {word!r} is too short")
        if key in ("abbreviations", "words", "non_name_words") and (" " in item or "*" in item):
            raise ValueError(f"{where}[{i}] must be a single word without '*'; "
                             f"use exclusions.phrases for {item!r}")
        out.append(item)
    return out


@dataclass(frozen=True)
class Exclusions:
    abbreviations: FrozenSet[str]
    words_lower: FrozenSet[str]
    legal_act_prefix: Pattern[str]
    skip_patterns: tuple  # CustomPattern (masking/custom.py)
    mask_patterns: tuple
    legal_acts: Tuple[str, ...]
    phrases: Tuple[str, ...]
    always_mask: Tuple[str, ...]
    added: int  # скільки записів додала конфігурація (для звіту — без самих слів)


def _patterns(items: List[str], name: str, action: str) -> tuple:
    # Імпорт тут: constants імпортує цей модуль, а custom — helpers → constants
    from datamasking.masking.custom import CustomPattern
    return tuple(
        CustomPattern(name=name,
                      regex=re.compile(_WORD_EDGE_BEFORE + "(?:" + phrase_regex(item) + ")"
                                       + _WORD_EDGE_AFTER, re.IGNORECASE),
                      group=0, action=action)
        for item in items)


def _base(dictionaries: Any, key: str, builtin: Tuple[str, ...]) -> Tuple[str, ...]:
    """Перелік із dictionaries.<key> (config.yaml) або вбудований, якщо ключа немає."""
    value = getattr(dictionaries, key, None) if not isinstance(dictionaries, dict) \
        else dictionaries.get(key)
    if value is None:
        return builtin
    return tuple(_items(dictionaries, key, "dictionaries"))


def build(section: Any = None, dictionaries: Any = None) -> Exclusions:
    """Переліки (dictionaries з config.yaml або вбудовані) + секція
    exclusions конфігурації. Raises ValueError."""
    lists = {key: _items(section, key) for key in KEYS}
    remove = {r.lower() for r in lists["remove"]}
    base_abbreviations = _base(dictionaries, "abbreviations", BUILTIN_ABBREVIATIONS)
    base_words = _base(dictionaries, "non_name_words", BUILTIN_WORDS)
    base_acts = _base(dictionaries, "legal_acts", BUILTIN_LEGAL_ACTS)

    abbreviations = frozenset(a.lower() for a in base_abbreviations if a.lower() not in remove) \
        | frozenset(a.lower() for a in lists["abbreviations"])
    words = frozenset(w.lower() for w in base_words if w.lower() not in remove) \
        | frozenset(w.lower() for w in lists["words"])
    acts = tuple(a for a in base_acts if a.lower() not in remove) \
        + tuple(lists["legal_acts"])
    if acts:
        legal = legal_act_regex(acts)
    else:
        legal = re.compile(r"(?!)")  # нічого не збігається
    return Exclusions(
        abbreviations=abbreviations,
        words_lower=words,
        legal_act_prefix=legal,
        # Назви актів із конфігурації теж не маскуються («Розпорядженням
        # Президента» з великої інакше береться за ПІБ); вбудовані — ні, щоб
        # не змінювати типові маски
        skip_patterns=(_patterns(lists["phrases"], "exclusions.phrases", "skip")
                       + _patterns(lists["legal_acts"], "exclusions.legal_acts", "skip")),
        mask_patterns=_patterns(lists["always_mask"], "exclusions.always_mask", "mask"),
        legal_acts=acts,
        phrases=tuple(lists["phrases"]),
        always_mask=tuple(lists["always_mask"]),
        added=sum(len(lists[k]) for k in KEYS if k != "remove"),
    )


def describe(ex: Exclusions) -> str:
    """Текст для --list-exclusions (діючі переліки)."""
    def block(title: str, items: Iterable[str]) -> List[str]:
        items = sorted(items)
        return [f"{title} ({len(items)}):", "  " + (", ".join(items) if items else "—"), ""]
    lines: List[str] = []
    lines += block("Abbreviations (never masked as a surname)", ex.abbreviations)
    lines += block("Words that are never part of a name", ex.words_lower)
    lines += block("Legal acts (a date after '<act> ... від' is kept)", ex.legal_acts)
    lines += block("Phrases never masked", ex.phrases)
    lines += block("Always masked", ex.always_mask)
    return "\n".join(lines).rstrip() + "\n"


def dictionaries_yaml(indent: str = "  ") -> str:
    """Секція dictionaries для config.yaml / --init-config із вбудованих переліків."""
    import json

    def flow(items: Iterable[str], per_line: int) -> str:
        quoted = [json.dumps(i, ensure_ascii=False) for i in items]
        rows = [", ".join(quoted[k:k + per_line]) for k in range(0, len(quoted), per_line)]
        inner = (",\n" + indent * 2).join(rows)
        return "[\n" + indent * 2 + inner + "\n" + indent + "]"

    return (f"{indent}abbreviations: {flow(BUILTIN_ABBREVIATIONS, 12)}\n"
            f"{indent}non_name_words: {flow(BUILTIN_WORDS, 6)}\n"
            f"{indent}legal_acts: {flow(BUILTIN_LEGAL_ACTS, 4)}\n")
