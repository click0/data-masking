#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Синтетичні маски прізвищ без витоку оригіналу (v3.0.2).

До 3.0.2 маска будувалась як original[:3] + випадкова середина + original[-5:]:
для прізвищ 5–8 літер префікс і суфікс перекривались, і ЦІЛЕ прізвище
лишалось видимим у масці (Ґудзь → Ґудузіґудзь, Коваль → Ковавриліоваль,
Сидоренко → Сидкоробренко). Це не маскування, а обфускація «на око».

Новий алгоритм:
  1. Поверхнева форма прізвища (з відмінковим закінченням, як у тексті)
     ділиться на ОСНОВУ + ЗАКІНЧЕННЯ за таблицею українських прізвищевих
     суфіксів (-енко/-енку, -ов/-ова/-ової, -ський/-ського, -ук/-ука …).
  2. Основа замінюється синтетичною — основою прізвища з faker (uk_UA),
     бажано тієї ж словотвірної родини (-енко → -енко) і схожої довжини.
  3. Закінчення оригіналу приєднується назад → відмінок і рід зберігаються
     («капітану Петренку» → «капітану Гриценку», «Іванова Марія» →
     «Грицова Марія»).
  4. Перевірки: маска ≠ оригінал, не містить оригінал/його основу,
     не збігається з жодною вже виданою маскою чи вже відомим оригіналом
     (колізія зламала б unmask). Детерміновано від seed(основа в нижньому
     регістрі): усі відмінкові форми й регістри одного прізвища дістають
     одну синтетичну основу (МАЗУРЕНКА / Мазуренко / Мазуренку).
"""

import random
import re
from typing import Dict, Iterable, Optional, Set, Tuple

from datamasking.masking import constants as _cfg
from datamasking.masking.helpers import get_deterministic_seed

# Закінчення → словотвірна родина. Порядок: довші першими (перший збіг).
# Основа після відрізання має бути ≥ MIN_STEM літер, інакше закінчення
# не вважається закінченням (щоб «Рак» не став «Р»+«ак»).
_ENDINGS: Tuple[Tuple[str, str], ...] = (
    # -енко (усі відмінки чоловічого роду; жіночий — незмінюване)
    ("енкові", "енко"), ("енком", "енко"), ("енка", "енко"), ("енку", "енко"), ("енко", "енко"),
    # -ський / -цький (прикметникові)
    ("ського", "ський"), ("ському", "ський"), ("ським", "ський"), ("ською", "ський"),
    ("ської", "ський"), ("ській", "ський"), ("ська", "ський"), ("ський", "ський"),
    ("цького", "цький"), ("цькому", "цький"), ("цьким", "цький"), ("цькою", "цький"),
    ("цької", "цький"), ("цькій", "цький"), ("цька", "цький"), ("цький", "цький"),
    # -ов / -ев / -єв / -ів / -ин (присвійні)
    ("овим", "ов"), ("овою", "ов"), ("ової", "ов"), ("овій", "ов"), ("ова", "ов"), ("ову", "ов"), ("ов", "ов"),
    ("евим", "ев"), ("евою", "ев"), ("евої", "ев"), ("евій", "ев"), ("ева", "ев"), ("еву", "ев"), ("ев", "ев"),
    ("євим", "єв"), ("євою", "єв"), ("євої", "єв"), ("євій", "єв"), ("єва", "єв"), ("єву", "єв"), ("єв", "єв"),
    ("івим", "ів"), ("івою", "ів"), ("івої", "ів"), ("івій", "ів"), ("іва", "ів"), ("іву", "ів"), ("ів", "ів"),
    # «-ином», «-инові» — орудний і давальний іменникової відміни (Литвином,
    # Литвинові); до 3.1.22 вони розбирались як основа «литвин» + «-ом», і
    # маска мала іншу основу, ніж «Литвин» / «Литвина»
    ("инові", "ин"), ("иним", "ин"), ("ином", "ин"), ("иною", "ин"), ("иної", "ин"), ("иній", "ин"),
    ("ина", "ин"), ("ину", "ин"), ("ин", "ин"),
    ("іним", "ін"), ("іною", "ін"), ("іної", "ін"), ("іній", "ін"), ("іна", "ін"), ("іну", "ін"), ("ін", "ін"),
    # -ук / -юк / -чук / -ак / -як / -ик / -ець / -ун (приголосні основи)
    ("укові", "ук"), ("уком", "ук"), ("ука", "ук"), ("уку", "ук"), ("ук", "ук"),
    ("юкові", "юк"), ("юком", "юк"), ("юка", "юк"), ("юку", "юк"), ("юк", "юк"),
    ("акові", "ак"), ("аком", "ак"), ("ака", "ак"), ("аку", "ак"), ("ак", "ак"),
    ("якові", "як"), ("яком", "як"), ("яка", "як"), ("яку", "як"), ("як", "як"),
    ("икові", "ик"), ("иком", "ик"), ("ика", "ик"), ("ику", "ик"), ("ик", "ик"),
    ("ецеві", "ець"), ("ецем", "ець"), ("еця", "ець"), ("ецю", "ець"), ("ець", "ець"),
    ("єцеві", "єць"), ("єцем", "єць"), ("єця", "єць"), ("єцю", "єць"), ("єць", "єць"),
    ("унові", "ун"), ("уном", "ун"), ("уна", "ун"), ("уну", "ун"), ("ун", "ун"),
    # -ко (Сірко, Бойко) — після -енко, щоб не перехопити
    ("кові", "ко"), ("ком", "ко"), ("ка", "ко"), ("ку", "ко"), ("ко", "ко"),
    # прикметникові -ий / -ій (Білий, Заболотній)
    ("ого", "ий"), ("ому", "ий"), ("им", "ий"), ("ий", "ий"), ("ій", "ий"),
    # жіночий родовий прикметникових (Білої, Довгої): до 3.1.20 включно не
    # розпізнавався, і маска «Білої» мала іншу основу, ніж «Біла» / «Білій»
    ("ої", "а"),
    # родові -а/-я (Сорока, Гмиря) та відмінкові -и/-і/-ою/-ею
    ("ою", "а"), ("ею", "я"), ("и", "а"), ("і", "а"), ("а", "а"), ("я", "я"),
    # інші відмінкові закінчення приголосних основ (Коваля, Ковалем, Ковалю)
    ("ові", ""), ("еві", ""), ("ом", ""), ("ем", ""), ("єм", ""), ("у", ""), ("ю", ""),
)

MIN_STEM = 3
_ATTEMPTS = 24
_FAKER_DRAWS = 12

# ---------------------------------------------------------------------------
# Словник документа: маска не має збігатися з жодним словом вхідного тексту
# (інакше unmask замінить і чужі входження — реальне прізвище іншої особи,
# яке ще не встигло потрапити в mapping, або звичайне слово). Рушій
# реєструє словник на час обробки документа; після виходу він очищується,
# щоб маски лишались детермінованими між документами.
# ---------------------------------------------------------------------------
_WORD_RE = re.compile(r"[А-ЯІЇЄҐа-яіїєґ][А-ЯІЇЄҐа-яіїєґ'’]+")
_document_vocab: Set[str] = set()
_document_long_words: Set[str] = set()
_document_text: str = ""
# Слова/числа документа (нижній регістр), які після маскування лишаться
# відкритими — визначає пробний прогін у engine (None — ще не визначено:
# тоді document_contains шукає по всьому тексту)
_residue_tokens: Optional[Set[str]] = None
_depth = 0


def enter_document(text: str) -> None:
    """Реєструє слова документа (зовнішній виклик); вкладені — лише лічильник."""
    global _depth, _document_vocab, _document_long_words, _document_text
    if _depth == 0:
        words = {m.group(0).lower() for m in _WORD_RE.finditer(text)}
        _document_vocab = words
        _document_long_words = {w for w in words if len(w) >= 5}
        _document_text = text
    _depth += 1


def set_residue(tokens: Optional[Set[str]]) -> None:
    """Слова/числа, що лишаться незамаскованими (нижній регістр); None — скинути."""
    global _residue_tokens
    _residue_tokens = tokens


def residue_vocabulary() -> Set[str]:
    """Слова, яких має уникати маска імені: ті, що лишаться відкритими
    (якщо визначено), інакше — всі слова документа."""
    return _residue_tokens if _residue_tokens is not None else _document_vocab


def document_contains(token: str) -> bool:
    """Чи лишиться *token* у документі відкритим словом/числом (без
    урахування регістру). Маска, що збігається з таким словом (звання
    «капітан» у «Командир роти капітан», число 778 у «778 одиниць», дата
    закону), після розмаскування мінялась місцями з ним (v3.1.9)."""
    if not _document_text or not token:
        return False
    if _residue_tokens is not None and " " not in token:
        return token.lower() in _residue_tokens
    before = r"(?<!\d)" if token[0].isdigit() else r"(?<![\w'’ʼ])"
    after = r"(?!\d)" if token[-1].isdigit() else r"(?![\w'’ʼ])"
    return re.search(before + re.escape(token) + after, _document_text, re.IGNORECASE) is not None


def exit_document() -> None:
    global _depth, _document_vocab, _document_long_words, _document_text
    _depth = max(0, _depth - 1)
    if _depth == 0:
        _document_vocab = set()
        _document_long_words = set()
        _document_text = ""
        set_residue(None)


def document_vocabulary() -> Set[str]:
    return _document_vocab


def split_surname(word: str) -> Tuple[str, str, str]:
    """Повертає (основа, закінчення, родина) для нижнього регістру *word*.

    Якщо жодне закінчення не підходить (Ґудзь, Коваль, Шамрай) —
    закінчення порожнє, основа = усе слово, родина "".
    """
    w = word.lower()
    for ending, family in _ENDINGS:
        if w.endswith(ending) and len(w) - len(ending) >= MIN_STEM:
            return w[: -len(ending)], ending, family
    return w, "", ""


_CONSONANTS = "бвгджзклмнпрстфхцчшщ"
_VOWELS = "аеиіоу"
# Родини, чиє закінчення приєднується до основи на приголосну: основа з
# м'яким знаком/й/голосною дала б «Заєцьуком», «Журавельий»
_CONSONANT_FAMILIES = frozenset({
    "енко", "ко", "ський", "цький", "ов", "ев", "єв", "ів", "ин", "ін",
    "ук", "юк", "ак", "як", "ик", "ець", "єць", "ун", "ий",
})


def _stem_fits(stem: str, family: str) -> bool:
    if family in _CONSONANT_FAMILIES:
        return stem[-1] in _CONSONANTS
    return True


def _draw_candidates(seed: int, bare: bool) -> Iterable[Tuple[str, str]]:
    """Кандидати з faker uk_UA: (основа, родина).

    Для «голих» оригіналів (без розпізнаного закінчення — Ґудзь, Коваль,
    Шамрай) кандидат — ЦІЛЕ faker-прізвище, інакше обрізана основа
    («Девдюк» → «Девд») виглядала б каліцтвом.
    """
    _cfg.fake_uk.seed_instance(seed)
    for _ in range(_FAKER_DRAWS):
        # Апостроф — ASCII «'», як у масках імен (v3.1.8): faker дає «ʼ»
        # (U+02BC), якого немає в cp1251, і документ у cp1251 з такою маскою
        # прізвища не зберігався (до 3.1.22)
        candidate = _cfg.fake_uk.last_name().lower().replace("ʼ", "'").replace("’", "'")
        if bare:
            if len(candidate) >= MIN_STEM and "'" not in candidate and " " not in candidate:
                yield candidate, ""
            continue
        stem, _ending, family = split_surname(candidate)
        if len(stem) >= MIN_STEM:
            yield stem, family


def _pick_stem(seed: int, target_len: int, family: str, ending: str, forbidden: Set[str],
               prefix: str = "", consonant_end: bool = False) -> str:
    """Обирає синтетичну основу: тієї ж родини, придатну до закінчення
    і схожої довжини, якщо є. Якщо задано *prefix* — основа починається
    з нього (перші символи оригінального прізвища), а решта синтетична."""
    same_family: list = []
    others: list = []
    p = len(prefix)
    for cand, fam in _draw_candidates(seed, bare=(ending == "")):
        # хвіст кандидата після префікса має бути хоч 2 символи, щоб маска
        # не була «префікс + 1 літера»
        if p and len(cand) < p + 2:
            continue
        # Стик префікса й хвоста має бути вимовним: після голосної —
        # приголосна і навпаки («іва»+«анов» → «іваанов», «тк»+«мак» → «ткмак» — ні)
        if p and not _joint_ok(prefix, cand[p:]):
            continue
        stem = prefix + cand[p:] if p else cand
        if stem in forbidden or not _stem_fits(stem, family):
            continue
        (same_family if fam == family and family else others).append(stem)

    def closest(pool):
        return min(pool, key=lambda s: abs(len(s) - target_len)) if pool else None

    # «Голе» прізвище на приголосний (Бондар, Мороз) — маска теж на
    # приголосний, якщо такий кандидат є: інші відмінки (Бондаря, Морозом)
    # беруть цю основу (paradigm_mask), і «Бонуба» давала б «Бонубая»
    if consonant_end:
        same_family = [s for s in same_family if s[-1] in _CONSONANTS] or same_family
        others = [s for s in others if s[-1] in _CONSONANTS] or others
    return closest(same_family) or closest(others) or _random_stem(seed, target_len, prefix)


_ALL_VOWELS = "аеиіоуюяєї"


def _joint_ok(prefix: str, tail: str) -> bool:
    """Голосна + приголосна (або навпаки) на стику; ь/й/апостроф — як приголосна."""
    if not prefix or not tail:
        return True
    last_vowel = prefix[-1] in _ALL_VOWELS
    first_vowel = tail[0] in _ALL_VOWELS
    return last_vowel != first_vowel


def _random_stem(seed: int, target_len: int, prefix: str = "") -> str:
    """Запасний варіант: вимовна псевдооснова з чергуванням приголосна/голосна
    (після *prefix*, якщо він є)."""
    rnd = random.Random(seed)
    length = max(MIN_STEM, min(target_len, 8))
    tail_len = max(2, length - len(prefix))
    start_with_vowel = bool(prefix) and prefix[-1] not in _ALL_VOWELS
    tail = "".join(
        rnd.choice(_VOWELS if (i % 2 == 0) == start_with_vowel else _CONSONANTS)
        for i in range(tail_len)
    )
    return prefix + tail


def prefix_length_for(original: str, configured: Optional[int] = None,
                      minimum: Optional[int] = None) -> int:
    """Скільки перших символів оригіналу лишити в масці.

    Правило (ТЗ): N з конфігу (SURNAME_PREFIX_LENGTH, типово 3), але з
    оригіналу в масці лишається НЕ БІЛЬШЕ ПОЛОВИНИ прізвища — і префікс,
    і збережене закінчення разом (v3.0.16; раніше закінчення не рахувалось,
    і в «Мазуренка → Мазиденка» збігались 7 із 9 літер). Половина береться
    від базової (називної) форми — основа + родинне закінчення, — щоб
    префікс не залежав від відмінка (Іванов / Іванова / Івановим → 1).

    Але не менше SURNAME_PREFIX_MIN (типово 2, v3.1.4/3.1.5): інакше прізвища на
    «-енко» лишались без жодної літери оригіналу. *minimum* — для тестів.

    Коваль → 3, Ґудзь → 2, Ткач → 2, Іванов → 1, Кравчук → 1,
    Бондаренко → 1, Петренко → 1 (за правилом половини було б 0).
    """
    n = _cfg.SURNAME_PREFIX_LENGTH if configured is None else configured
    if n <= 0:
        return 0
    lo = _cfg.SURNAME_PREFIX_MIN if minimum is None else minimum
    stem, _ending, family = split_surname(original)
    base_len = len(stem) + len(family)
    budget = base_len // 2 - len(family)
    p = max(min(n, budget), min(lo, n))
    # Хоча б один символ основи має змінитись (Лис-енко: основа «лис» — префікс
    # 2, не 3), інакше маска містить усю основу і no-leak відкидає всі спроби
    return max(0, min(p, len(stem) - 1))


def _leaks(masked: str, original: str, stem: str) -> bool:
    """Маска не має розкривати оригінал: ні цілком, ні основою (≥ MIN_STEM),
    і не має містити жодного довгого слова документа (чуже прізвище)."""
    m, o = masked.lower(), original.lower()
    if m == o or o in m or (len(m) >= MIN_STEM and m in o):
        return True
    if len(stem) >= MIN_STEM and stem in m:
        return True
    # Підрядки маски довжиною ≥5 проти множини довгих слів документа:
    # O(len(m)^2) lookup-ів замість перебору всього словника на кожну спробу
    if _document_long_words:
        for i in range(len(m)):
            for j in range(i + 5, len(m) + 1):
                if m[i:j] in _document_long_words:
                    return True
    return False


# Відміна на приголосний (Коваль, Ткач, Бондар): закінчення її відмінків
# (-а/-я, -у/-ю, -ем) збігаються з закінченнями родин «-а»/«-я» (Сорока,
# Гмиря), і без словника форма «Ткача» не відрізняється від «Сороки». Тож
# кожна форма діставала свою синтетичну основу: Коваль → Ковар, але
# Коваля → Кобіля (до 3.1.22). У межах документа форма бере основу з маски
# іншої форми того самого прізвища, якщо та вже є
_PLAIN_FAMILIES = frozenset({"", "а", "я"})


def _plain_paradigm(word: str) -> Optional[Tuple[str, str]]:
    """(основа без м'якого знака, закінчення) для прізвищ «простих» родин,
    інакше None. «коваль» → («ковал», ""), «коваля» → («ковал», «я»)."""
    stem, ending, family = split_surname(word.lower())
    if family not in _PLAIN_FAMILIES:
        return None
    if not ending and stem.endswith("ь"):
        stem = stem[:-1]
    return (stem, ending) if len(stem) >= MIN_STEM else None


# Закінчення відмінка — за останнім приголосним нової основи: після
# задньоязикових і губних — тверді (Ткака → Ткака, Ткаком), після шиплячих —
# «-а/-у/-ем» (Ткача, Ткачем), після інших — як в оригіналі (Коваря, Ковар)
_HARD_ONLY = frozenset("кгґхпбфвм")
_HUSHING = frozenset("жчшщ")
_TO_HARD = {"я": "а", "ю": "у", "ем": "ом", "єм": "ом", "еві": "ові"}
_TO_HUSHING = {"я": "а", "ю": "у", "ом": "ем", "єм": "ем", "ові": "еві"}


def _harmonize(ending: str, stem: str) -> str:
    last = stem[-1:]
    if last in _HARD_ONLY:
        return _TO_HARD.get(ending, ending)
    if last in _HUSHING:
        return _TO_HUSHING.get(ending, ending)
    return ending


def paradigm_mask(original: str, masking_dict: Dict, forbidden: Set[str]) -> Optional[str]:
    """Маска (нижній регістр) для *original* з основою маски іншої форми того
    самого прізвища в цьому документі — або None, якщо такої форми немає чи
    похідна маска не годиться (витік, збіг зі словом документа)."""
    own = _plain_paradigm(original)
    if own is None:
        return None
    stem, ending = own
    for other, info in masking_dict.get("mappings", {}).get("surname", {}).items():
        if not isinstance(info, dict) or not info.get("masked_as") or other.lower() == original.lower():
            continue
        theirs = _plain_paradigm(other)
        if theirs is None or theirs[0] != stem:
            continue
        other_mask = str(info["masked_as"]).lower()
        other_ending = theirs[1]
        if other_ending and not other_mask.endswith(other_ending):
            continue
        new_stem = other_mask[:len(other_mask) - len(other_ending)] if other_ending else other_mask
        new_stem = new_stem[:-1] if new_stem.endswith("ь") else new_stem
        # Основа на голосну з відмінковим закінченням — «Бонубая», «Мойдаа»
        if not new_stem or "-" in new_stem or (ending and new_stem[-1] not in _CONSONANTS):
            continue
        masked = new_stem + _harmonize(ending, new_stem)
        if original.lower().endswith("ь") and not ending and new_stem[-1:] in _CONSONANTS:
            masked += "ь"   # Коваль → Кобіль, як Коваля → Кобіля
        if (not _leaks(masked, original, split_surname(original)[0])
                and masked not in forbidden and masked not in _document_vocab):
            return masked
    return None


def known_surname_forms(masking_dict: Dict, except_original: Optional[str] = None) -> Set[str]:
    """Усі вже відомі оригінали та маски прізвищ (нижній регістр) —
    нова маска не повинна з ними збігатися, інакше unmask неоднозначний.

    *except_original* — маски інших регістрових форм ТОГО Ж прізвища
    (Сидоренко / СИДОРЕНКО) не заборонені: вони мають дати ту саму основу
    (до 3.1.9 ВЕЛИКА форма діставала іншу основу)."""
    forms: Set[str] = set()
    same = (except_original or "").lower()
    for original, info in masking_dict.get("mappings", {}).get("surname", {}).items():
        forms.add(original.lower())
        if isinstance(info, dict) and info.get("masked_as") and original.lower() != same:
            forms.add(info["masked_as"].lower())
    return forms


def synthesize_surname(original: str, forbidden: Optional[Set[str]] = None,
                       prefix_length: Optional[int] = None) -> str:
    """Детермінована синтетична маска (нижній регістр) для поверхневої форми *original*.

    Зберігає перші N символів оригіналу (див. prefix_length_for) і його
    відмінкове/родове закінчення; не містить оригінал і не збігається з
    жодним рядком із *forbidden*.
    """
    forbidden = {f.lower() for f in (forbidden or set())} | _document_vocab
    stem, ending, family = split_surname(original)
    # Seed — від основи в нижньому регістрі, а не від поверхневої форми:
    # «рядового МАЗУРЕНКА» у шапці й «Мазуренко І.П.» у тексті — одна людина,
    # тож МАЗУРЕНКА / Мазуренка / Мазуренко / Мазуренку мають діставати одну
    # синтетичну основу (закінчення й регістр накладаються окремо)
    base_seed = get_deterministic_seed(stem)
    prefix = original.lower()[:prefix_length_for(original, prefix_length)]

    last = ""
    for attempt in range(_ATTEMPTS):
        seed = base_seed if attempt == 0 else get_deterministic_seed(f"{stem}\x00{attempt}")
        new_stem = _pick_stem(seed, len(stem), family, ending, forbidden={stem}, prefix=prefix,
                              consonant_end=(not ending and not family
                                             and (stem[-1:] in _CONSONANTS or stem.endswith("ь"))))
        masked = new_stem + ending
        last = masked
        if not _leaks(masked, original, stem) and masked not in forbidden:
            return masked

    # Теоретично недосяжно (24 спроби × 12 faker-кандидатів), але краще
    # гарантовано унікальна форма, ніж витік
    suffix = _random_stem(base_seed ^ 0xA5A5, 3)
    return last + suffix
