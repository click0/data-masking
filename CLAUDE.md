# CLAUDE.md — інструкції для сесій Claude Code у цьому репозиторії

## Перше, що зробити в новому клоні

```bash
git config core.hooksPath .githooks        # хук дописує блок атрибуції до комітів із Claude Code
pip install -e '.[full]' && pip install -r requirements-dev.txt
```

У хмарному контейнері системний `cryptography` буває зламаний (`_cffi_backend`
відсутній) — тоді: `pip install --force-reinstall --ignore-installed cryptography cffi`.

## Мова спілкування

Відповідати користувачу **українською**. Код, коміти, CHANGELOG — англійською
(коментарі в коді можуть бути українською, як у наявному коді).

## Правила комітів

- **Кожен коміт бампає patch-версію** у двох місцях: `datamasking/_version.py`
  та літерал `__version__` у `data_masking.py` (CI звіряє їх). Плюс запис у
  `CHANGELOG.md` під новим `## [X.Y.Z]`.
- Трейлери в кінці повідомлення — повний блок атрибуції:
  ```
  Co-Authored-By: Claude <Model> <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_<id>
  Generated-With: Claude Code <version>
  ```
  **`Co-Authored-By` — модель, яка робить САМЕ ЦЕЙ коміт** (код і коміти в
  одній сесії можуть писати різні моделі; модель перемикають посеред сесії).
  Назви моделі в оточенні немає, тому передавати її явно при кожному коміті:
  `git commit --trailer "Co-Authored-By: Claude <Model> <noreply@anthropic.com>" ...`.
  Хук (`core.hooksPath`) явний трейлер не чіпає й сам дописує
  `Claude-Session` (`CLAUDE_CODE_REMOTE_SESSION_ID` без `cse_`) і
  `Generated-With` (`CLAUDE_CODE_VERSION`); без явного трейлера ставить
  узагальнене `Claude <noreply@anthropic.com>` і попереджає.
- Ніяких ідентифікаторів моделі в коді, коментарях чи PR-описах — лише в трейлері.

## Робочий процес

1. Гілка розробки — **постійна**: `claude/refactor-data-masking-lIcWN`.
   Перед новою задачею синхронізувати з `main`
   (`git fetch origin main && git checkout -B claude/refactor-data-masking-lIcWN origin/main`).
   Гілку не видаляти і не пересоздавати (проксі не пропускає `push --delete`,
   та й потреби немає: PR мержаться merge-комітом, тож після мержу гілка —
   предок `main`, а не «побічна»).
2. Перед комітом: `python -m pytest tests/ -q -p no:cacheprovider`,
   `python -m mypy datamasking/ --config-file mypy.ini` (має бути 0 помилок —
   джоба blocking), `flake8 . --select=E9,F63,F7,F82`.
3. Push → PR у `main` → дочекатись **зеленого CI на всій матриці**
   (Linux 3.9/3.11/3.13, Windows 3.12, core-only, package, mypy) →
   **merge-коміт (`merge_method: merge`), НЕ squash**: так GitHub позначає
   гілку як merged, а в графі `main` видно кожен merge. Після мержу —
   синхронізувати гілку з `main` (п. 1).
4. Стежити за CI через GitHub API за **повним SHA** (`?head_sha=<40 hex>`);
   скорочений SHA API ігнорує.
5. **Теги через проксі не пушаться** — релізи створює користувач: Releases →
   «Draft a new release» → тег `vX.Y.Z` → Publish. `release.yml` сам збирає
   все, додає файли, `SHA256SUMS` і атестацію походження, а опис бере з
   `CHANGELOG.md` (усі записи після попереднього тегу,
   `.github/scripts/release_notes.py`). Опис, написаний у формі вручну, не
   перезаписується. Тому **CHANGELOG — це і є реліз-нотес**: записи пишемо
   англійською так, щоб їх можна було читати користувачу. Без запису для
   поточної версії тест падає на кожному push, а реліз — до публікації.

## Архітектура (коротко)

- Пакет `datamasking/`: `masking/` (рушій, `surname.py` — синтетичні прізвища з
  префіксом оригіналу), `unmasking/`, `extras/` (config, security, selective,
  re_mask, tools, logger, password_generator), `rank_data.py`, `diagnose.py`.
- Кореневі `masking/`, `unmasking/`, `modules/`, `rank_data.py` — **shim-и**
  зворотної сумісності (DeprecationWarning), у wheel не потрапляють.
- `datamasking/__init__.py` навмисно легкий (без faker) — `diagnose` має
  лишатись stdlib-only.
- Mapping-файли: unmask залежить лише від mapping, не від алгоритму маскування,
  тому зміни масок не ламають розмаскування старих файлів
  (`tests/fixtures/legacy_mappings/` — реальні файли v2.3.0/v2.5.1/v2.6.5).

## Інваріанти, які перевіряють тести — не ламати

- Маска прізвища: перші N символів оригіналу (N = `SURNAME_PREFIX_LENGTH`;
  префікс + збережене закінчення ≤ половини базової форми прізвища, хоча б
  один символ основи змінюється) + синтетична основа + закінчення; **ніколи**
  не містить оригінал, його основу чи слово документа; детермінована від
  seed(основа в нижньому регістрі) — усі регістри й відмінки одного прізвища
  дають одну синтетичну основу.
- Імена/по батькові ніколи не мапляться самі на себе.
- Дати ДД.ММ.РРРР розпізнаються для 1900–2100 (дати народження теж), зсув
  ніколи не нульовий; межі 2015–2035 — лише для зсуву дат документів. Дата
  нормативного акта («Закону України від …») не чіпається.
- Новий ключ конфігурації — лише разом із кодом, що його читає
  (`EFFECTIVE_KEYS` у `extras/config.py`), тестом і рядком у прикладах;
  ключі поза `EFFECTIVE_KEYS` і `PLANNED_KEYS` дають попередження при завантаженні.
- Нереалізовані опції лишаються в прикладах з позначкою `[не реалізовано]`
  (`PLANNED_KEYS`, план — `docs/TODO-config-options.md`). Реалізували — перенести
  ключ у `EFFECTIVE_KEYS`, зняти позначку, виправити значення в прикладі, якщо
  воно не збігається з фактичною поведінкою (таблиця в TODO).
  З v3.0.30 `PLANNED_KEYS` порожній. Ключі, що описують незмінну поведінку
  (`ALWAYS_ON_KEYS`: `consistent_mapping`, `save_chain` тощо), приймають лише
  `true`; інше значення — помилка конфігурації з поясненням.
- Шари конфігурації: `config.yaml` (або `config.py`) → `config_local.yaml`
  (тека користувача, потім поруч із `config.yaml`) → ENV → CLI. Значення
  не-null з локального файлу перекриває спільне, секції зливаються, списки
  замінюються. Тести не мають читати справжню теку користувача —
  `conftest.isolate_user_config_dir` підміняє `XDG_CONFIG_HOME`/`APPDATA`.
- `config.yaml` у корені — **спільний конфіг, комітиться**: усі ключі зі
  значеннями за замовчуванням (дані = `config_example.yaml`) і повні переліки
  виключень (`dictionaries`). З ним маски мають бути такими самими, як без
  конфігу. `masking/exclusions.py` (`BUILTIN_*`) — запасна копія переліків
  (без PyYAML / інший конфіг); тест звіряє її з `config.yaml`, тож змінюючи
  перелік — міняти обидва місця. Секція `exclusions` переліки доповнює.
  Приватне — лише в `config_local.yaml` (шаблон `config_local.example.yaml`).
- `--encrypt` пише лише `.enc` (plaintext mapping не створюється), mapping —
  атомарно з правами 0600.
- Формат `.enc` 1 (PBKDF2, сіль 16) — за замовчуванням, його читають усі версії;
  формат 2 (заголовок `DMENC2`, scrypt або інша сіль) — лише за явного
  `security.key_derivation`/`salt_length`. Читання розпізнає обидва.
- Коди виходу: 0 успіх, 1 помилка, 2 неправильне використання; жодних
  traceback-ів на очікуваних помилках.
- Тести, що потребують cryptography/pyyaml, мають `skipif` (є CI-джоба
  core-only без них).

## Файли, яких не має бути в репо

`config_local.yaml` (будь-де), `output_*`, `masking_map_*`, `masking_report_*`,
`input_recovery_*`, `input.txt` (усе в `.gitignore`; фікстури тестів названі
інакше — `source.txt`). `conftest.py` падає, якщо тест змінює кореневий `config.yaml` або лишає
`config_local.yaml`.
