# CLAUDE.md — інструкції для сесій Claude Code у цьому репозиторії

## Перше, що зробити в новому клоні

```bash
git config core.hooksPath .githooks        # хук додає Co-Authored-By до комітів із Claude Code
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
- Трейлери в кінці повідомлення — повний блок атрибуції (хук додає його
  сам, якщо `core.hooksPath` увімкнено; інакше — вручну):
  ```
  Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_<id>
  Generated-With: Claude Code <version>
  ```
  (`<id>` — `CLAUDE_CODE_REMOTE_SESSION_ID` без префікса `cse_`;
  версія — `CLAUDE_CODE_VERSION`.)
- Ніяких ідентифікаторів моделі в коді, коментарях чи PR-описах — лише в трейлері.

## Робочий процес

1. Гілка розробки — тимчасова, одна на задачу, з фіксованим ім'ям
   `claude/refactor-data-masking-lIcWN`: створюється від `origin/main`
   (`git checkout -B claude/refactor-data-masking-lIcWN origin/main`), після
   squash-мержу PR має зникнути з origin, щоб між задачами лишався лише
   `main`. **Видалити її з цього середовища неможливо** — проксі відхиляє
   `git push --delete` (як і теги), а GitHub API-інструменти видалення гілок
   не мають. Тому видалення робить GitHub: у репозиторії має бути ввімкнено
   Settings → General → Pull Requests → *Automatically delete head branches*
   (або власник видаляє гілку вручну на сторінці Branches). Не намагатись
   видаляти гілку з Claude Code — це марно. Наступна задача створює гілку
   знову від актуального `main` (force-push поверх старої, якщо GitHub її
   ще не прибрав, — нормально: вона містить лише вже змержену історію).
2. Перед комітом: `python -m pytest tests/ -q -p no:cacheprovider`,
   `python -m mypy datamasking/ --config-file mypy.ini` (має бути 0 помилок —
   джоба blocking), `flake8 . --select=E9,F63,F7,F82`.
3. Push → PR у `main` → дочекатись **зеленого CI на всій матриці**
   (Linux 3.9/3.11/3.13, Windows 3.12, core-only, package, mypy) → squash-merge
   (гілку прибирає GitHub, п. 1).
4. Стежити за CI через GitHub API за **повним SHA** (`?head_sha=<40 hex>`);
   скорочений SHA API ігнорує.
5. **Теги через проксі не пушаться** — релізи створює користувач вручну
   (тег `vX.Y.Z` запускає `release.yml`, який збирає й публікує все сам). Текст
   реліз-нотесу — англійською, після завершення пайплайна (він перезаписує опис).

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

- Маска прізвища: перші N символів оригіналу (N = `SURNAME_PREFIX_LENGTH`,
  не більше половини слова, хоча б один символ основи змінюється) + синтетична
  основа + закінчення; **ніколи** не містить оригінал, його основу чи слово
  документа; детермінована від seed(оригінал).
- Імена/по батькові ніколи не мапляться самі на себе.
- `--encrypt` пише лише `.enc` (plaintext mapping не створюється), mapping —
  атомарно з правами 0600.
- Коди виходу: 0 успіх, 1 помилка, 2 неправильне використання; жодних
  traceback-ів на очікуваних помилках.
- Тести, що потребують cryptography/pyyaml, мають `skipif` (є CI-джоба
  core-only без них).

## Файли, яких не має бути в репо

`config.yaml` у корені, `output_*`, `masking_map_*`, `masking_report_*`,
`input_recovery_*`, `input.txt` (усе в `.gitignore`; фікстури тестів названі
інакше — `source.txt`). `conftest.py` падає, якщо тест лишає `config.yaml`.
