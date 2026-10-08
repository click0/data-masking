#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Відмінювання імен і по батькові (v3.1.12).

До 3.1.12 маска імені будувалась від самої форми («Петра» → seed «Петра»),
відмінок визначався без урахування роду («Петра» → «жіноче ім'я в
називному»), а по батькові завжди маскувалось у називному. Через це
«капітана Петренка Петра Івановича» ставало «лейтенанта Пебоженка Павло
Лук'янович», а «Петро» й «Петра» в одному документі діставали різні маски.

Тут: форма → (називний відмінок, відмінок, рід) — ``analyze_name`` /
``analyze_patronymic``; називний відмінок маски → потрібна форма —
``decline_name`` / ``decline_patronymic``. Усі відмінки одного імені зводяться
до одного називного, тож маска одна («Петро/Петра/Петром» → «Павло/Павла/
Павлом»). Для називного відмінка результат збігається з попередніми версіями.
"""

import re
from typing import List, NamedTuple, Optional, Set, Tuple

from datamasking.masking import constants as _cfg

# Відмінки: nominative, genitive (= accusative для істот чоловічого роду),
# dative (також місцевий), dative_ovi («Петрові», «Андрієві»), accusative
# (жіночий: «Тетяну»), instrumental, vocative.
NOMINATIVE = 'nominative'
GENITIVE = 'genitive'
DATIVE = 'dative'
DATIVE_OVI = 'dative_ovi'
ACCUSATIVE = 'accusative'
INSTRUMENTAL = 'instrumental'
VOCATIVE = 'vocative'

_HUSHERS = ('ж', 'ч', 'ш', 'щ')
_VOWELS = 'аеєиіїоуюя'

# Чоловічі імена з м'яким -р (Ігоря, Ігорю, Ігорем — не Ігора)
_SOFT_R_NAMES = frozenset({'ігор', 'лазар', 'цезар'})

# Поширені імена (називний, нижній регістр) — доповнюють словники faker
# uk_UA: з них визначається називний відмінок і рід форми без підказки.
_BUILTIN_MALE = (
    "іван петро олег андрій сергій олександр михайло василь володимир микола юрій "
    "віктор дмитро максим ігор тарас богдан роман артем денис євген костянтин павло "
    "станіслав ярослав олексій анатолій валерій віталій геннадій григорій леонід "
    "валентин вадим владислав в'ячеслав руслан назар остап пилип мирослав святослав "
    "степан семен антон борис арсен данило кирило марко матвій тимофій федір яків "
    "захар захарій ілля лука кузьма хома микита сава мирон нестор омелян опанас "
    "панас едуард ростислав любомир зеновій зіновій орест лев гліб давид адам ян "
    "богуслав болеслав альберт артур вікентій веніамін герман ігнат йосип климентій "
    "корній лаврентій макар мар'ян мартин нікіта олесь прохор радомир самійло сидір "
    "спиридон терентій тихон трохим устим феодосій юліан юхим ярема демид дем'ян "
    "лук'ян гаврило георгій зиновій аркадій леонтій венедикт станислав стефан теодор "
    "аурел вілен владлен добромир дорофій іларіон ілларіон іполит касян кирил клим "
    "лесь лонгин людвіг макарій мефодій модест никифор овсій олелько онисим онуфрій "
    "орхип охрім пантелеймон пармен пахом порфир родіон ромуальд северин сильвестр "
    "симон соломон тадей тиміш трофим фелікс філімон флор харитон християн юстим "
    "ярополк денис євстахій євгеній сергей дмитрий николай"
).split()

_BUILTIN_FEMALE = (
    "анна ганна марія олена ірина тетяна наталія наталя оксана світлана юлія людмила "
    "надія валентина лариса ольга софія діана алла любов катерина вікторія галина "
    "дарія дарина анастасія вероніка віра ангеліна аліна альона богдана валерія "
    "василина зоряна зоя іванна інна кристина христина ксенія лілія леся лідія "
    "маргарита марина мар'яна мирослава неля ніна олеся орися поліна роксолана "
    "руслана сніжана соломія таїсія уляна яна ярина ярослава євгенія єлизавета "
    "єлисавета емілія жанна злата карина луїза мілана оленка раїса регіна рената "
    "римма роза стефанія тамара теодора тереза феодосія юстина антоніна антонія "
    "аврора агата агнеса адріана аделіна богуслава владислава володимира станіслава "
    "елла ельвіра емма іда ілона інга іраїда калина клавдія лада лана лія любомира "
    "магдалина меланія мотря нонна одарка оксенія олександра ореста павлина параска "
    "пелагея пріска радмила сабіна серафима сусанна устина фаїна флора хрестина "
    "ярославна аделаїда альбіна амалія анжела аніта варвара віолетта данна едита "
    "еріка златослава камілла ліза марта маруся михайлина мілена орина святослава "
    "євдокія єва ада ірена анжеліка валентина вікторія юліана ульяна оксана соломія"
).split()

_MALE_NAMES: Optional[Set[str]] = None
_FEMALE_NAMES: Optional[Set[str]] = None


def _normalize(word: str) -> str:
    return word.replace("ʼ", "'").replace("’", "'").lower()


def _faker_names() -> Tuple[Set[str], Set[str]]:
    """Імена зі словників faker uk_UA (не поточної локалі: граматика — українська)."""
    try:
        from faker.providers.person.uk_UA import Provider  # type: ignore
    except Exception:  # pragma: no cover — faker без uk_UA
        return set(), set()
    male = {_normalize(n) for n in getattr(Provider, 'first_names_male', ())}
    female = {_normalize(n) for n in getattr(Provider, 'first_names_female', ())}
    return male, female


def known_names(gender: str) -> Set[str]:
    """Відомі імена в називному відмінку (нижній регістр)."""
    global _MALE_NAMES, _FEMALE_NAMES
    if _MALE_NAMES is None or _FEMALE_NAMES is None:
        fm, ff = _faker_names()
        male = set(_BUILTIN_MALE) | fm | {_normalize(n) for n in _cfg.GOOD_UKRAINIAN_NAMES_MALE}
        female = set(_BUILTIN_FEMALE) | ff | {_normalize(n) for n in _cfg.GOOD_UKRAINIAN_NAMES_FEMALE}
        # Імена, що є в обох переліках (Валентина — жіноче; «Валентина» як
        # родовий від Валентин розбирається через підказку роду)
        _MALE_NAMES, _FEMALE_NAMES = male, female
    return _MALE_NAMES if gender == 'male' else _FEMALE_NAMES


class NameForm(NamedTuple):
    nominative: str   # називний відмінок, нижній регістр
    case: str
    gender: str       # 'male' | 'female'
    known: bool       # називний знайдено у переліку імен


def _pick(candidates: List[str], case: str, names: Set[str], strict: bool,
          default: Optional[str] = None) -> Optional[Tuple[str, str, bool]]:
    for c in candidates:
        if c in names:
            return c, case, True
    if strict:
        return None
    return (default if default is not None else candidates[-1]), case, False


def _soft_default(stem: str) -> str:
    """Називний для м'якої основи: голосна → -й (Андрій), інакше -ь (Василь)."""
    if stem in _SOFT_R_NAMES:
        return stem
    return stem + ('й' if stem and stem[-1] in _VOWELS else 'ь')


def _male_form(f: str, names: Set[str], strict: bool) -> Optional[Tuple[str, str, bool]]:
    """Форма чоловічого імені → (називний, відмінок, відомий). *strict* —
    лише коли називний знайдено в переліку (рід ще не відомий)."""
    if f in names:
        return f, NOMINATIVE, True
    n = len(f)
    if n >= 4 and f.endswith(('ом', 'ем', 'єм')):
        stem = f[:-2]
        if f.endswith('єм'):
            cands = [stem + 'й']
        elif f.endswith('ем'):
            cands = [stem + 'ь', stem]
        else:
            cands = [stem + 'о', stem]
        return _pick(cands, INSTRUMENTAL, names, strict)
    if n >= 4 and f.endswith(('ою', 'ею')):
        # Миколою, Іллею — без підказки роду лише відомі (інакше це жіночий орудний)
        stem = f[:-2]
        return _pick([stem + ('а' if f.endswith('ою') else 'я')], INSTRUMENTAL, names, strict)
    if n >= 5 and f.endswith(('ові', 'еві', 'єві')):
        stem = f[:-3]
        if f.endswith('єві'):
            cands = [stem + 'й']
        elif f.endswith('еві'):
            cands = [stem + 'ь', stem]
        else:
            cands = [stem + 'о', stem]
        return _pick(cands, DATIVE_OVI, names, strict)
    if n >= 3 and f.endswith('у'):
        stem = f[:-1]
        return _pick([stem + 'о', stem], DATIVE, names, strict)
    if n >= 3 and f.endswith('ю'):
        stem = f[:-1]
        return _pick([stem + 'й', stem + 'ь', stem], DATIVE, names, strict, _soft_default(stem))
    if n >= 3 and f.endswith('а'):
        stem = f[:-1]
        return _pick([stem + 'о', stem], GENITIVE, names, strict)
    if n >= 3 and f.endswith('я'):
        stem = f[:-1]
        return _pick([stem + 'й', stem + 'ь', stem], GENITIVE, names, strict, _soft_default(stem))
    if n >= 3 and f.endswith('и'):
        # Миколи, Сави, Микити — родовий імен на -а
        return _pick([f[:-1] + 'а'], GENITIVE, names, strict)
    if n >= 3 and f.endswith('і'):
        stem = f[:-1]
        return _pick([stem + 'а', stem + 'я'], DATIVE, names, strict, stem + 'а')
    if n >= 3 and f.endswith('е'):
        # Кличний: Петре, Іване, Олеже (г→ж), Марку? (-у, збігається з давальним)
        stem = f[:-1]
        cands = [stem + 'о', stem]
        if stem.endswith('ж'):
            cands += [stem[:-1] + 'г', stem[:-1] + 'го']
        elif stem.endswith('ч'):
            cands += [stem[:-1] + 'к', stem[:-1] + 'ко']
        elif stem.endswith('ш'):
            cands += [stem[:-1] + 'х']
        return _pick(cands, VOCATIVE, names, strict, stem)
    if n >= 3 and f.endswith('о'):
        # Миколо (кличний від -а) або невідоме ім'я на -о в називному
        if f[:-1] + 'а' in names:
            return f[:-1] + 'а', VOCATIVE, True
        return (None if strict else (f, NOMINATIVE, False))
    return None if strict else (f, NOMINATIVE, False)


def _female_form(f: str, names: Set[str], strict: bool) -> Optional[Tuple[str, str, bool]]:
    """Форма жіночого імені → (називний, відмінок, відомий)."""
    if f in names:
        return f, NOMINATIVE, True
    n = len(f)
    if n >= 4 and f.endswith('ою'):
        return _pick([f[:-2] + 'а'], INSTRUMENTAL, names, strict)
    if n >= 4 and f.endswith('ею'):
        stem = f[:-2]
        return _pick([stem + 'я', stem + 'а'], INSTRUMENTAL, names, strict,
                     stem + ('а' if stem.endswith(_HUSHERS) else 'я'))
    if n >= 4 and f.endswith('єю'):
        return _pick([f[:-2] + 'я'], INSTRUMENTAL, names, strict)
    if n >= 3 and f.endswith('и'):
        return _pick([f[:-1] + 'а'], GENITIVE, names, strict)
    if n >= 3 and f.endswith('ї'):
        # Марії, Зої, Наталії — родовий = давальний
        return _pick([f[:-1] + 'я'], GENITIVE, names, strict)
    if n >= 3 and f.endswith('і'):
        stem = f[:-1]
        # Любові (III відміна) → Любов; чергування перед -і: Ользі → Ольга,
        # Вероніці → Вероніка, Мотрусі → Мотруха
        cands = [stem + 'а', stem + 'я', stem]
        if stem.endswith('з'):
            cands.append(stem[:-1] + 'га')
        elif stem.endswith('ц'):
            cands.append(stem[:-1] + 'ка')
        elif stem.endswith('с'):
            cands.append(stem[:-1] + 'ха')
        return _pick(cands, DATIVE, names, strict, stem + 'а')
    if n >= 4 and f.endswith("'ю"):
        # Любов'ю
        return _pick([f[:-2]], INSTRUMENTAL, names, strict)
    if n >= 3 and f.endswith('у'):
        return _pick([f[:-1] + 'а'], ACCUSATIVE, names, strict)
    if n >= 3 and f.endswith('ю'):
        return _pick([f[:-1] + 'я'], ACCUSATIVE, names, strict)
    if n >= 3 and f.endswith('о'):
        return _pick([f[:-1] + 'а'], VOCATIVE, names, strict)
    if n >= 3 and f.endswith('є'):
        return _pick([f[:-1] + 'я'], VOCATIVE, names, strict)
    if f.endswith(('а', 'я')):
        return None if strict else (f, NOMINATIVE, False)
    # Любов, Нінель — не відмінюються тут
    return None if strict else (f, NOMINATIVE, False)


def _legacy_case_and_gender(name_lower: str) -> Tuple[str, str]:
    """Евристика до 3.1.12 — запасний варіант для невідомих імен без підказки роду."""
    if name_lower.endswith(('ом', 'ем', 'єм', 'ім', 'їм')): return INSTRUMENTAL, 'male'
    if name_lower.endswith(('у', 'ю')) and not name_lower.endswith(('ою', 'єю', 'ією')): return DATIVE, 'male'
    if name_lower.endswith(('а', 'я')) and len(name_lower) > 4:
        common_female_endings = ['ія', 'ла', 'на', 'ра', 'та', 'ка', 'га', 'ва', 'ня', 'ся', 'ша']
        if not any(name_lower.endswith(e) for e in common_female_endings): return GENITIVE, 'male'
    if name_lower.endswith(('ією', 'ою', 'єю')): return INSTRUMENTAL, 'female'
    if name_lower.endswith(('і', 'ї')) and len(name_lower) > 3: return DATIVE, 'female'
    if name_lower.endswith(('ія', 'а', 'я')) and len(name_lower) > 2: return NOMINATIVE, 'female'
    return NOMINATIVE, 'male'


def analyze_name(form: str, gender_hint: Optional[str] = None,
                 case_hint: Optional[str] = None) -> NameForm:
    """Форма імені → називний відмінок, відмінок і рід.

    *gender_hint* — рід від по батькові («Петра Івановича» → чоловічий
    родовий, а не «жіноче ім'я Петра»); *case_hint* — відмінок по батькові,
    яким знімається неоднозначність форми («Наталі Петрівни» — родовий,
    «Наталі Петрівні» — давальний).
    """
    f = _normalize(form).strip('.,!?;:')
    if not f:
        return NameForm(f, NOMINATIVE, gender_hint or 'male', False)
    male, female = known_names('male'), known_names('female')
    result: Optional[Tuple[str, str, bool]] = None
    gender = gender_hint if gender_hint in ('male', 'female') else None
    if gender == 'male':
        result = _male_form(f, male, strict=False)
    elif gender == 'female':
        result = _female_form(f, female, strict=False)
    else:
        # Без підказки роду: усі прочитання з відомим називним, у порядку
        # «жіноче ім'я як є» (Тетяна, Богуслава) → «чоловіче як є» (Микола)
        # → чоловіча форма (Петра → Петро) → жіноча форма (Тетяни → Тетяна).
        # Відмінок звання («рядового … Богуслава») обирає прочитання з тим
        # самим відмінком: родовий від Богуслав, а не називний Богуслава.
        readings: List[Tuple[Tuple[str, str, bool], str]] = []
        if f in female and f not in male:
            readings.append(((f, NOMINATIVE, True), 'female'))
        if f in male:
            readings.append(((f, NOMINATIVE, True), 'male'))
        r = _male_form(f, male, strict=True)
        if r is not None and r[1] != NOMINATIVE:
            readings.append((r, 'male'))
        r = _female_form(f, female, strict=True)
        if r is not None and r[1] != NOMINATIVE:
            readings.append((r, 'female'))
        if readings:
            chosen = readings[0]
            if case_hint:
                for reading in readings:
                    if _same_case(reading[0][1], case_hint, reading[1]):
                        chosen = reading
                        break
            result, gender = chosen
        else:
            # Невідоме ім'я: евристика за закінченням, як до 3.1.12
            gender = _legacy_case_and_gender(f)[1]
            if gender == 'male':
                result = _male_form(f, male, strict=False)
            else:
                result = _female_form(f, female, strict=False)
    assert result is not None and gender is not None
    nominative, case, known = result
    if case_hint and (case, case_hint) in _AMBIGUOUS_OVERRIDES:
        # Закінчення імені неоднозначне (-і/-ї: родовий чи давальний,
        # -у/-ю: давальний чи кличний) — відмінок по батькові чи звання точніший
        case = case_hint
    return NameForm(nominative, case, gender, known)


# (відмінок за закінченням імені, відмінок-підказка) → підказка перекриває
_AMBIGUOUS_OVERRIDES = frozenset({
    (DATIVE, GENITIVE), (GENITIVE, DATIVE), (DATIVE, VOCATIVE),
    (GENITIVE, ACCUSATIVE), (DATIVE, DATIVE_OVI),
})


def _same_case(case: str, hint: str, gender: str) -> bool:
    if case == hint:
        return True
    if {case, hint} == {DATIVE, DATIVE_OVI}:
        return True
    if gender == 'male' and {case, hint} == {GENITIVE, ACCUSATIVE}:
        return True
    return False


def decline_name(nominative: str, case: str, gender: str) -> str:
    """Називний відмінок імені → потрібна форма (нижній або будь-який регістр;
    закінчення додається в нижньому)."""
    name = nominative.strip()
    if not name or case == NOMINATIVE:
        return name
    low = _normalize(name)
    if gender == 'male':
        if low.endswith('о'):
            stem = name[:-1]
            return stem + {GENITIVE: 'а', DATIVE: 'у', DATIVE_OVI: 'ові', ACCUSATIVE: 'а',
                           INSTRUMENTAL: 'ом', VOCATIVE: 'е'}[case]
        if low.endswith('а'):
            stem = name[:-1]
            return stem + {GENITIVE: 'и', DATIVE: 'і', DATIVE_OVI: 'і', ACCUSATIVE: 'у',
                           INSTRUMENTAL: 'ою', VOCATIVE: 'о'}[case]
        if low.endswith('я'):
            stem = name[:-1]
            return stem + {GENITIVE: 'і', DATIVE: 'і', DATIVE_OVI: 'і', ACCUSATIVE: 'ю',
                           INSTRUMENTAL: 'ею', VOCATIVE: 'е'}[case]
        if low.endswith('й'):
            stem = name[:-1]
            return stem + {GENITIVE: 'я', DATIVE: 'ю', DATIVE_OVI: 'єві', ACCUSATIVE: 'я',
                           INSTRUMENTAL: 'єм', VOCATIVE: 'ю'}[case]
        if low.endswith('ь') or low in _SOFT_R_NAMES:
            stem = name[:-1] if low.endswith('ь') else name
            return stem + {GENITIVE: 'я', DATIVE: 'ю', DATIVE_OVI: 'еві', ACCUSATIVE: 'я',
                           INSTRUMENTAL: 'ем', VOCATIVE: 'ю'}[case]
        # тверда приголосна: Олег, Іван, Тарас
        if case == VOCATIVE:
            if low.endswith('г'): return name[:-1] + 'же'
            if low.endswith('к'): return name + 'у'
            if low.endswith('х'): return name[:-1] + 'ше'
            if low.endswith(_HUSHERS): return name + 'е'
            return name + 'е'
        return name + {GENITIVE: 'а', DATIVE: 'у', DATIVE_OVI: 'ові', ACCUSATIVE: 'а',
                       INSTRUMENTAL: 'ом'}[case]
    # female
    if low.endswith('я'):
        stem = name[:-1]
        if len(low) >= 2 and low[-2] in _VOWELS:
            # Марія, Зоя, Наталія: -ї/-ї/-ю/-єю/-є
            return stem + {GENITIVE: 'ї', DATIVE: 'ї', DATIVE_OVI: 'ї', ACCUSATIVE: 'ю',
                           INSTRUMENTAL: 'єю', VOCATIVE: 'є'}[case]
        return stem + {GENITIVE: 'і', DATIVE: 'і', DATIVE_OVI: 'і', ACCUSATIVE: 'ю',
                       INSTRUMENTAL: 'ею', VOCATIVE: 'ю'}[case]
    if low.endswith('а'):
        stem = name[:-1]
        husher = low[-2:-1] in _HUSHERS
        if case == DATIVE or case == DATIVE_OVI:
            if low.endswith('га'): return name[:-2] + 'зі'
            if low.endswith('ка'): return name[:-2] + 'ці'
            if low.endswith('ха'): return name[:-2] + 'сі'
            return stem + 'і'
        return stem + {GENITIVE: ('і' if husher else 'и'), ACCUSATIVE: 'у',
                       INSTRUMENTAL: ('ею' if husher else 'ою'), VOCATIVE: 'о'}[case]
    if low.endswith(('б', 'п', 'в', 'м', 'ф', 'л', 'н', 'р', 'с', 'т', 'д', 'з', 'ь')):
        # III відміна: Любов — Любові, Любов'ю; Нінель — Нінелі, Нінеллю (спрощено)
        if low.endswith('ь'):
            name, low = name[:-1], low[:-1]
        if case in (GENITIVE, DATIVE, DATIVE_OVI):
            return name + 'і'
        if case == INSTRUMENTAL:
            return name + ("'ю" if low[-1] in 'бпвмф' and len(low) > 1 and low[-2] in _VOWELS else 'ю')
        if case == VOCATIVE:
            return name + 'е'
        return nominative.strip()  # знахідний = називний
    # Іншомовні на -і/-о тощо — без зміни
    return name


_FEMALE_PATRONYMIC = (
    ('івною', INSTRUMENTAL), ('ївною', INSTRUMENTAL),
    ('івна', NOMINATIVE), ('ївна', NOMINATIVE), ('івни', GENITIVE), ('ївни', GENITIVE),
    ('івні', DATIVE), ('ївні', DATIVE), ('івну', ACCUSATIVE), ('ївну', ACCUSATIVE),
    ('івно', VOCATIVE), ('ївно', VOCATIVE),
)
_MALE_PATRONYMIC = (
    ('ичем', INSTRUMENTAL), ('ічем', INSTRUMENTAL),
    ('ича', GENITIVE), ('іча', GENITIVE), ('ичу', DATIVE), ('ічу', DATIVE),
    ('ич', NOMINATIVE), ('іч', NOMINATIVE),
)
_PATRONYMIC_RE = re.compile(r"^[а-яіїєґ']+$")


class PatronymicForm(NamedTuple):
    nominative: str   # нижній регістр
    case: str
    gender: str       # 'male' | 'female' | 'unknown'


def analyze_patronymic(form: str) -> PatronymicForm:
    """Форма по батькові → називний (нижній регістр), відмінок, рід."""
    f = _normalize(form).strip('.,!?;:')
    if not f or not _PATRONYMIC_RE.match(f):
        return PatronymicForm(f, NOMINATIVE, 'unknown')
    for suffix, case in _FEMALE_PATRONYMIC:
        if f.endswith(suffix) and len(f) > len(suffix):
            return PatronymicForm(f[:-len(suffix)] + suffix[:3] + 'а', case, 'female')
    for suffix, case in _MALE_PATRONYMIC:
        if f.endswith(suffix) and len(f) > len(suffix):
            return PatronymicForm(f[:-len(suffix)] + suffix[:2], case, 'male')
    return PatronymicForm(f, NOMINATIVE, 'unknown')


def decline_patronymic(nominative: str, case: str) -> str:
    """Називний відмінок по батькові → потрібна форма (рід — за закінченням)."""
    p = nominative.strip()
    if not p or case == NOMINATIVE:
        return p
    low = _normalize(p)
    if low.endswith(('ич', 'іч')):
        return p + {GENITIVE: 'а', ACCUSATIVE: 'а', DATIVE: 'у', DATIVE_OVI: 'у',
                    INSTRUMENTAL: 'ем', VOCATIVE: 'у'}[case]
    if low.endswith('на'):
        return p[:-1] + {GENITIVE: 'и', DATIVE: 'і', DATIVE_OVI: 'і', ACCUSATIVE: 'у',
                         INSTRUMENTAL: 'ою', VOCATIVE: 'о'}[case]
    return p
