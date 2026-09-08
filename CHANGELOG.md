# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [3.0.13] - 2026-09

### Changed — tooling
- `CLAUDE.md`: back to a single persistent working branch; PRs are merged
  with a merge commit (not squash) so the branch is marked merged and the
  merges are visible in the `main` graph — no branch deletion needed.

## [3.0.12] - 2026-09

### Changed — tooling
- `prepare-commit-msg` hook now writes the full attribution block instead
  of a single line: `Co-Authored-By`, `Claude-Session` (URL derived from
  `CLAUDE_CODE_REMOTE_SESSION_ID`) and `Generated-With: Claude Code <version>`
  (from `CLAUDE_CODE_VERSION`); each trailer is added only if missing.
  Documented in `.githooks/README.md`, `docs/INSTALL.md`, `CLAUDE.md`.

## [3.0.11] - 2026-09

### Changed — tooling
- `CLAUDE.md`: branch deletion cannot be done from the Claude Code
  environment (the git proxy rejects `push --delete`, like tags) — the
  repository should have GitHub's *Automatically delete head branches*
  enabled; sessions must not try to delete branches themselves.

## [3.0.10] - 2026-09

### Changed — tooling
- `CLAUDE.md`: the working branch is now temporary — created from `main`
  per task and deleted on origin after the squash-merge, so no side
  branches linger between tasks.

## [3.0.9] - 2026-09

### Added — tooling
- Versioned git hooks in `.githooks/` (enable with
  `git config core.hooksPath .githooks`): `prepare-commit-msg` appends the
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` trailer to
  commits made from a Claude Code session (`CLAUDECODE` env), idempotently;
  merge/squash commits untouched; co-author overridable via
  `git config claude.coauthor`. Documented in INSTALL.md.
- `CLAUDE.md`: per-repository instructions for Claude Code sessions (enable
  the hooks on a fresh clone, commit/version rules, workflow, invariants
  the tests protect, release procedure).

## [3.0.8] - 2026-09

### Added — surname prefix and faker locale (requirements)
- **Surname masks keep the first characters of the original again.** The
  3.0.2 synthetic algorithm dropped the leading letters the old
  `original[:3]…` formula had preserved implicitly. Now the mask =
  first N characters of the original + synthetic stem + the original's
  grammatical ending (`Петренку → Петаченку`, `Іванова → Іварунова`,
  `Ґудзь → Ґузій`). N defaults to 3; **short surnames keep at most half
  of the word** (`Ґудзь → 2`, `Ткач → 2`, `Рак → 1`). The prefix is taken
  from the surface form regardless of where the ending starts, but never
  reaches into the ending. All no-leak checks stay in force (mask never
  equals/contains the original, its stem, or any document word); the
  prefix/stem joint is kept pronounceable (vowel + consonant).
- **`masking_rules.surname_prefix_length`** (YAML) /
  **`DATA_MASKING_SURNAME_PREFIX_LENGTH`** (ENV): the N above; `0`
  restores fully synthetic masks (3.0.2–3.0.7 behaviour); negative or
  non-integer values are a fatal config error.
- **`system.faker_locale`** (YAML) / **`DATA_MASKING_FAKER_LOCALE`**
  (ENV), default `uk_UA`: the faker dictionaries used for synthetic
  surname stems, given-name fallbacks and patronymics. Ukrainian
  morphology (surname endings, rank declension, patronymic gender) is
  unchanged; locales without patronymics (most of them) fall back to
  `uk_UA` for patronymics; an unknown locale is rejected at start-up.
  `Faker('uk_UA')` is no longer hard-wired at import — see
  `constants.set_faker_locale()`.
- Tests: `tests/test_surname_prefix.py` (prefix lengths incl. short
  surnames, ending/case preservation, hyphenated parts, pronounceable
  joint, YAML/ENV wiring, locale switch, unknown locale, patronymic
  fallback).

### Compatibility
- Surname masks differ from 3.0.2–3.0.7 (same input → new, stable masks).
  Unmasking of files from any earlier version is unaffected.

## [3.0.7] - 2026-09

### Changed — static typing: mypy is clean and blocking
- All 58 mypy errors fixed (`mypy datamasking/` → 0). Mostly honest
  annotations: `Optional[...]` where `None` really flows
  (`gender_hint`, `patronymic_hint`, `exclude`, `max_size`, `password`),
  typed empty containers, a `TypedDict` for rank matches in the unmask
  engine, `isinstance` guards after `json.load`. The CI mypy job is now
  **blocking** (was advisory).

### Fixed — found by the type checker
- **`unmask_data.py --to-version` was dead code**: it called
  `ChainUnmasker.convert_to_version`, which does not exist, and passed a
  dict where a `MappingChain` is expected — every invocation crashed with
  `TypeError`. Reimplemented as partial chain restore: `--to-version N`
  unmasks a `--re-mask` output back to the state after pass N
  (0 = original); non-chain mappings and out-of-range N are rejected.
  `unmask_chain(..., to_version=N)` added to the engine.
- `ChainUnmasker._apply_reverse_pass` (extras API) treated mapping values
  (`{"masked_as": …}` dicts) as strings and ignored instance tracking, so
  it could never restore text — it now delegates to the real unmask
  engine. `get_chain_info` accepts a chain dict as well as a
  `MappingChain` (the CLI always passed a dict).
- Tests: `tests/test_to_version.py` (engine, CLI, `ChainUnmasker`,
  `get_chain_info`).

## [3.0.6] - 2026-09

### Fixed — rank restore with overlapping forms (`--re-mask` chain bug)
- `unmask_ranks_gender_aware` collected every rank form found in the
  text, including a shorter form nested inside a longer one
  (`майстер-сержант` inside `головний майстер-сержант`). Both consumed an
  instance number, so a genuine standalone occurrence of the short form
  got a non-existent instance and was skipped or restored to the wrong
  rank. This surfaced with `--re-mask`, where masks of different passes
  overlap as substrings (pass 2: `лейтенант → головний майстер-сержант`
  and `головний майстер-сержант → майстер-сержант`) — reproduced on
  `input_example.txt`. Matches are now taken longest-first without
  overlap; the 2-pass chain restore of `input_example.txt` is identical to
  the single-pass restore. Tests: `tests/test_chain_unmask.py`.

## [3.0.5] - 2026-09

### Changed — CI, packaging, release pipeline, docs (audit items 13–14, 16, 20–21)
- **CI** (`ci.yml`): runs on every branch push and PR; test matrix
  ubuntu 3.9/3.11/3.13 + **windows 3.12** (the exe is a release target,
  so tests must pass there too); the package is `pip install -e '.[full]'`-ed
  and console scripts/`python -m datamasking` are exercised; new
  **core-only job** (faker only) proves encryption/YAML tests skip
  rather than fail and that `--encrypt` degrades with a clean error;
  **package job** builds wheel+sdist, runs `twine check`, extracts the
  sdist and runs the test suite inside it, and asserts the wheel contains
  only `datamasking`; advisory (non-blocking) mypy job; coverage now
  targets `datamasking`.
- **Release** (`release.yml`): restructured into `build-python` +
  `build-windows` (parallel) → `publish` (tag only, needs both). The
  GitHub release is created only after the Windows exe exists — a
  PyInstaller failure no longer leaves a release without the zip
  INSTALL.md points to. Version/tag check and pre-release detection are
  done once and shared; source archives now include
  `pyinstaller_utf8_hook.py`, `CHANGELOG.md`, `MANIFEST.in`, `mypy.ini`;
  the Windows roundtrip test also covers `--encrypt` (only `.enc` written,
  restored via `DATA_MASKING_PASSWORD`).
- **Packaging**: `MANIFEST.in` makes the sdist self-contained and
  testable (root wrappers, shims, tests with `conftest.py`, `pytest.ini`);
  `license = "BSD-3-Clause"` + `license-files` (PEP 639, setuptools ≥ 77)
  replaces the deprecated table form and classifier; `requirements.txt`
  documents core vs optional deps and no longer pulls pytest.
- `--encrypt` without the `cryptography` package is refused up front with
  a clear message (exit 1) instead of failing after the output was written.
- Tests that need cryptography/pyyaml carry `skipif` markers (core
  install: 690 passed, 24 skipped; full: 713 passed).
- **Docs**: README EN/UK describe the real output names
  (`output_*`, `masking_map_*`, `masking_report_*`, `input_recovery_*`,
  next to `-o`), use the `-i` flag in every example; `__main__.py`
  docstring no longer advertises the invalid `python -m data-masking`.
- `.pre-commit-config.yaml`: mypy hook was always failing with "Missing
  target module" (now targets `datamasking`); out-of-sync isort hook removed.

## [3.0.4] - 2026-09

### Fixed — configuration & environment (audit item 9)
- `DATA_MASKING_*` environment overrides were ignored unless a
  `config.yaml` existed (the loader was never run); the loader now always
  runs, so the documented priority CLI > ENV > YAML > defaults holds.
- `DATA_MASKING_PASSWORD` was mapped onto `security.password_env_var`,
  i.e. the *password value* was stored where a *variable name* belongs and
  the documented variable was never used for encryption. The mapping is
  removed (the CLI reads the variable directly); a new
  `DATA_MASKING_PASSWORD_ENV_VAR` sets the variable name.
- Malformed YAML or a non-mapping document used to be swallowed (defaults
  applied, "Loaded config" printed, exit 0) — now a fatal error; an
  explicitly given `--config` that does not exist is fatal too.
- `security.encrypt_output: true` and `validation.max_input_size_mb`
  were documented but dead — now wired (`encrypt_output` ≡ `--encrypt`).
- The CLI's own config template disagreed with the loader schema
  (`security.password_generation: true` replaced the dataclass with a
  bool; "AES-128-CBC via Fernet" text) — the CLI now delegates to the
  single loader template, and a bare bool is accepted as
  `password_generation.enabled`.
- Python config is loaded only from `./config.py` (never an arbitrary
  `config` module found on `sys.path`, which `python -m datamasking` made
  trivially possible).

### Fixed — CLI details
- `data_masking.py` gained the same Windows UTF-8 stdout fix as unmask
  (the `✅` summary raised `UnicodeEncodeError` on cp1252 consoles after
  files were already written).
- Output/mapping/report name suffix is re-rolled when a clash exists
  (two runs within one second could silently overwrite each other).
- `encrypt_mapping` rejects an empty password; `estimate_crack_time` no
  longer overflows on very long passwords; unmask treats `.JSON` like
  `.json`.

### Fixed — test suite hygiene (audit items 11–12)
- `conftest.py` no longer deletes the developer's `config.yaml` from the
  repository root after every test (it now fails a test that leaves one
  behind) and restores `os.environ` instead of popping every `DM_*`.
- ~12 tests that could not fail (`except Exception: assert True`,
  `assert X in [True, False]`, `… or True`, silent `pytest.skip` on CLI
  failure) rewritten as real in-process assertions; 8 new config/ENV tests.

## [3.0.3] - 2026-09

### Fixed — recognition leaks (audit item 4)
- **Hyphenated surnames** (`Петренко-Іванова`, `Нечуй-Левицький`) were not
  recognised at all (capital letter after the hyphen failed the name
  check) — the whole PIB stayed in clear text. Both parts must now look
  like names; the mask keeps the `X-Y` structure with a synthetic mask per
  part; mixed-case restore no longer lower-cases such surnames.
- **Full PIB after the same person's initials** (`Іванов П.А. … Іванов
  Петро Андрійович`) stayed in clear text: the parser only tried the first
  capitalised anchor and, when it yielded fewer than two words (e.g. the
  already-masked initials form), abandoned the whole line. It now tries
  every anchor in the line. A PIB is accepted only if it appears verbatim
  in the line (no more phantom mapping entries and idle iterations), and a
  punctuation mark after a word ends the PIB (`Сергійович, ІПН …`).
- **Rank + bare surname** (`рядовий Іванов прибув`, `капітан Петренко`,
  `підполковнику Сидоренку`) is now masked — a rank is strong enough
  context for a single following surname. Without a rank a lone
  capitalised word is still left alone.
- **Surname that is also a rank word** (`капітан Майор Іван Іванович`)
  is masked as a surname when it is Title-case, directly follows a real
  rank and precedes a name.
- **Text dates with a quoted day** (`«31» грудня 2025 року`, the most
  common form in orders) masked fine but never unmasked: the mapping key
  has no quotes while the text does. The unmask alternation now tolerates
  quotes/spaces around the day and restores the date keeping the quotes.
- **Patronymic gender**: `-евич`, `-ич`, `-іч` (Їжакевич, Ілліч, Кузьмич,
  Лукич) are male — previously "unknown", which produced a feminine mask.
- **Given names mapped to themselves**: Марія, Юлія, Катерина, Тетяна,
  Ірина (and any name that is the only whitelist entry for its first
  letter) were returned unchanged as their own "mask". The original is now
  excluded from candidates; if no other name starts with the same letter,
  any other name is used.
- **All-caps PIB** (`ІВАНОВ ПЕТРО МИКОЛАЙОВИЧ`) had surname and name
  swapped; the "emphasised surname" heuristic now applies only when the
  first word is not itself upper-case.
- `ІПН`, `РНОКПП`, `паспорт` added to the exclude list (were accepted as
  name-like words).
- Bonus: mixed-case-safe case restoration also fixed the long-standing
  `БР 123/… → бр 123/…` loss on unmask — legacy fixtures now restore
  byte-exact (former xfail tests are now regular tests).

### Performance
- Overlap checks in the item collector were O(items²) (`any(...)` over
  all collected spans per candidate) and took ~60% of masking time on
  large files; replaced by position-coverage bytearrays. 5000-line
  benchmark: masking is faster than 3.0.2 despite the broader parser.

### Tests
- `tests/test_recognition.py` (≈55 tests) covering every case above plus
  official-text non-regression.

## [3.0.2] - 2026-09

### Fixed — surname masks no longer reveal the original (audit item 3)
- Up to 3.0.1 a surname mask was `original[:3] + random middle +
  original[-5:]`; for 5–8-letter surnames prefix and suffix overlapped and
  the **whole original was readable inside the mask** (`Ґудзь →
  Ґудузіґудзь`, `Коваль → Ковавриліоваль`, `Сидоренко → Сидкоробренко`,
  `ПЕТРО → ПЕТАЛЕНПЕТРО`). Masks are now fully synthetic
  (`datamasking/masking/surname.py`): the surface form is split into
  stem + inflectional ending by a table of Ukrainian surname suffixes
  (-енко/-енку, -ов/-ова/-ової, -ський/-ського, -ук/-ука, -єць, …), the
  stem is replaced by a faker-derived stem of the same family and similar
  length, and the original ending is re-attached — so grammatical case and
  gender are preserved (`капітану Петренку → капітану Гайденку`,
  `Іванова Марія → Юхимова Марія`). Bare surnames (Ґудзь, Коваль, Шамрай)
  get a whole synthetic surname.
- Collision protection: the engine registers the document's vocabulary
  before masking, and a mask is rejected if it equals any word of the
  document or contains any 5+-letter document word — a mask can no longer
  coincide with another person's real surname (which would make unmask
  replace their occurrences too), regardless of the order in which the
  surnames appear. Checks also reject masks equal to already issued
  masks/originals and masks containing the original or its stem.
- Still deterministic (seeded by the original); the vocabulary is cleared
  after each document so identical inputs give identical mappings.

### Compatibility
- Surname masks differ from those produced by ≤ 3.0.1 (same input → new
  but stable masks). Unmasking of files produced by any earlier version is
  unaffected — it uses the mapping file, not the algorithm (legacy-fixture
  tests for v2.3.0/v2.5.1/v2.6.5 pass unchanged).

### Tests
- `tests/test_surname_mask.py` (≈120 tests): no-leak for the previously
  leaky cases, stem invisibility, endings preserved across cases/genders,
  determinism, no collision with any document word, vocabulary cleared
  between documents, case preservation, whitelist, roundtrips.

## [3.0.1] - 2026-09

Security/CLI hardening after the 3.0.0 audit. All items below were
confirmed reproducible on 3.0.0 and are now covered by in-process CLI tests.

### Fixed — CRITICAL
- **`--encrypt` left the plaintext mapping on disk.** `masking_map_*.json`
  with every original value was written first and never removed; `.enc`
  was written next to it. Now only the `.enc` file is written — plaintext
  never touches the disk. Mapping files (json and enc) are written
  atomically with mode 0600.
- **Encrypted mappings could not be restored via CLI at all**:
  `unmask_data.py … --map x.enc` crashed with `TypeError` on every run
  (`MappingSecurityManager(password)` / missing password argument in
  `unmasking/io.py`, broken since 2.5.0).
- **`--only` silently masked nothing.** The CLI had its own type table
  (`ranks`, `names`, …) that disagreed with `--list-types`/`selective.py`
  (`rank`, `name`, …) and with the README comma form; an unknown name
  only warned while every `MASK_*` flag was already cleared → output
  byte-identical to input, exit 0. `--only/--exclude` now go through
  `extras.selective` (canonical names, plurals, Ukrainian aliases, groups,
  comma or space separated); an unknown type is a usage error (exit 2)
  and nothing is written. `--list-types` prints groups and aliases.
- **`--re-mask N --encrypt` ignored `--encrypt`** and wrote the chain in
  plaintext; the summary also printed a `masking_map_*.json` path that
  was never written. The chain is now written as `masking_chain_*.enc`
  when encrypting and the summary shows the real file.

### Fixed — data safety
- `-o` refuses to point at the input file and refuses to overwrite an
  existing file without `--force` (previously `-i in.txt -o in.txt`
  destroyed the original silently). `--init-config` likewise no longer
  clobbers an existing `config.yaml` without `--force`.
- Mapping and report are written next to the `-o` output (previously
  always in cwd, so unmask auto-pairing could not find them).
- Password handling: `--password-env VAR` with an unset/empty variable is
  a fatal error before any file is written (previously a random password
  was silently generated); empty `--password` rejected; both CLIs read
  `DATA_MASKING_PASSWORD` by default (legacy `MASKING_PASSWORD` /
  `UNMASK_PASSWORD` still accepted on the unmask side).
- Exit codes: `main()` returns 0/1/2 and all entry points
  (`data_masking.py`, `unmask_data.py`, `python -m datamasking`, console
  scripts) propagate it — errors no longer exit 0. Unmask catches
  `ValueError`/`RuntimeError` (bad schema, wrong password, missing
  cryptography) as clean messages instead of tracebacks; `-c FILE`
  without `--password` no longer crashes on the Config dataclass.

### Added — tests
- `tests/test_cli_inprocess.py` (27 tests): mask→unmask through
  `main(argv)` in `tmp_path` for txt/json, `--encrypt` (+ wrong password,
  env var on both sides, generated password to stderr), `--only`
  (canonical/plural/Ukrainian/comma, unknown type), `--exclude`,
  `--re-mask` (plain and encrypted chain), `-o` safety, exit codes.
- `tests/fixtures/legacy_mappings/{v2.3.0,v2.5.1,v2.6.5}/` — REAL
  output/mapping/recovered files produced by the code at those git tags,
  with `tests/test_legacy_mappings.py` asserting current unmask restores
  the original input (case-insensitive) and does not regress vs the old
  version's own restore. Note: v2.3.0's own unmask left 24 lines
  unrestored; current code restores them.

### Known (documented as xfail / next)
- `БР 123/…` restores as `бр 123/…` — case of the BR prefix is lost on
  restore (long-standing, all versions).
- Multi-pass (`--re-mask`) unmask can restore a wrong rank when rank
  masks of different passes overlap as substrings (e.g. pass 2 maps both
  `лейтенант → головний майстер-сержант` and
  `головний майстер-сержант → майстер-сержант`); reproduced on
  `input_example.txt`, single-line cases are fine.

## [3.0.0] - 2026-07

**Major release: пакетна структура.** Повна зворотна сумісність:
старі імпорти працюють через shim-и, mapping-файли 2.x розмасковуються
без змін, CLI-скрипти та їхні аргументи не змінилися.

### Changed — BREAKING (import paths)
- Увесь код переїхав в один top-level пакет **`datamasking`**:
  `masking/` → `datamasking/masking/`, `unmasking/` → `datamasking/unmasking/`,
  `modules/` → `datamasking/extras/`, `rank_data.py` → `datamasking/rank_data.py`,
  `diagnose_mapping.py` → `datamasking/diagnose.py`. Це прибирає загальні
  top-level імена (`modules`, `rank_data`), які конфліктували б у
  site-packages.
- Старі пласкі шляхи (`import masking`, `from modules.tools import …`,
  `from rank_data import …`) працюють з checkout репозиторію через
  кореневі shim-и з `DeprecationWarning`; `sys.modules`-аліаси гарантують
  єдиний стан модулів (живі прапорці `MASK_*` спільні для обох шляхів).
  У wheel shim-и не потрапляють.

### Added — packaging
- **`pyproject.toml`**: `pip install .`; extras `[security]` (cryptography),
  `[yaml]` (pyyaml), `[full]`, `[dev]`; ядро залежить лише від faker.
- **Console scripts**: `data-mask`, `data-unmask`, `data-masking-diagnose`;
  запуск модулем: `python -m datamasking mask|unmask`.
- Єдине джерело версії — `datamasking/_version.py` (без імпортів,
  setuptools читає статично).

### Changed — release pipeline
- `release.yml` переписано під нову структуру: PyInstaller
  hidden-imports `datamasking.*`, збірка та публікація wheel+sdist,
  smoke-тест wheel (console scripts + перевірка, що shim-и не втекли у
  site-packages), реальний mask→unmask roundtrip зібраних Windows-exe
  з перевіркою маскування/відновлення ІПН, dry-run режим
  (`workflow_dispatch`) з будь-якої гілки без тега, dev-версії
  автоматично позначаються pre-release.

### Fixed
- `check_mapping_version` відправляв mapping версії 3.x у v1-логіку
  розмаскування; major/minor тепер парсяться числами (те саме у
  валідації схеми `unmasking/io.py`, включно з major ≥ 10).
- Застарілий кореневий `__init__.py` змушував PyInstaller шукати модулі
  в батьківській директорії — Windows-exe збирався без пакета; файл
  видалено, усі PyInstaller-виклики отримали явний `--paths=.`.
- `datamasking/__init__` ліниво делегує метадані (PEP 562):
  `diagnose_mapping.py` знову stdlib-only і не потребує faker.
- `extras/re_mask.py` штампував захардкоджену версію "2.6.0" у нові
  chain-mapping; сім модулів `extras/*` несли застарілі локальні
  `__version__` — всюди єдина версія пакета.

### Documentation
- README (EN/UK) і INSTALL.md переписані під пакетну структуру:
  pip-установка з extras, консольні команди, приклади
  `datamasking.extras.*`, оновлені інструкції локальної PyInstaller-збірки.

## [2.6.10] - 2026-07

### Removed
- Rank **«рекрут»** removed from all rank lists: `RANK_DECLENSIONS`,
  `ARMY_RANKS` (rank_data.py), army regex in `RANK_PATTERNS`
  (masking/constants.py) and its copy in `modules/tools.py`, plus README
  rank tables and examples. The rank is no longer recognized in text and
  is never produced as a mask.

### Note
- Removing «рекрут» from the army hierarchy shifts deterministic mask
  choices for adjacent low ranks — the same input text may now mask ranks
  differently than in ≤2.6.9. Unmasking of old files is unaffected:
  it uses the mapping JSON, not the hierarchy.

## [2.6.9] - 2026-07

### Fixed
- Official letter openings are no longer masked as PIB:
  `Повідомляємо Вам, що …` was treated as "Surname Name". Words with
  1st/2nd-person-plural verb endings (`-ємо`, `-имо`, `-емо`, `-єте`,
  `-ите`, `-ете`) are rejected as name candidates; pronouns
  `Вам/Вами/Ваш(-а/-е)` and common verbs (`Повідомляємо`, `Просимо`,
  `Направляємо`, `Надаємо`) added to `EXCLUDE_WORDS`. Real PIB after such
  phrases is still masked.

## [2.6.8] - 2026-07

### Added
- **Standalone ranks in quotes are now masked.** A rank wrapped in quotes as
  a value on its own — `«молодший сержант»`, `звання «капітан» присвоєно`,
  or log lines `… → «молодший сержант» …` — is masked even without an
  accompanying PIB. Only exact known rank forms (`ALL_RANK_FORMS`) inside the
  quotes are touched; arbitrary quoted text (`«важливо»`, `«138»`) is left
  alone. Quotes stay in place; unmask restores via the `rank` mapping.

### Known limitation
- If a masked rank happens to collide with a *different, unmasked* bare rank
  elsewhere in the same line (e.g. `капітан «майор»` where `майор` masks to
  `капітан`), roundtrip may be ambiguous — an inherent property of
  deterministic masking on collisions, not specific to quotes. Realistic
  formats (one quoted rank, or several distinct quoted ranks) round-trip
  correctly.

## [2.6.7] - 2026-07

### Fixed
- **PIB preceded by service labels / noise is now masked.** In lines like
  `ПІБ: Петренко Іван Васильович` or log lines
  `… ІПН=3698521592 — ПІБ «138» → «Міронов Андрій Петрович» …` the real name
  was skipped: the PIB anchor latched onto `ІПН=…` (starts uppercase) or the
  marker `ПІБ`, then stopped. Now `is_pib_anchor` strips trailing punctuation
  and rejects tokens containing digits/`=`; `ПІБ` and `звання` are excluded
  markers.

### Known limitation
- A bare rank with **no** following PIB (e.g. `звання «…» → «молодший сержант»`)
  is still not masked — long-standing behavior that avoids false positives on
  rank words in prose; independent of this fix.

## [2.6.6] - 2026-06

### Fixed
- **Quoted values are now masked.** Names, rank+PIB and IPNs wrapped in quotes
  (`«…»`, `"…"`, `„…“`) were skipped because words stuck to the quote chars
  (`«Петренко`, `сержант»`) and only `,.!?;:` was stripped. Quotes are now
  stripped in recognition (`looks_like_name`, `is_pib_anchor`,
  `is_likely_surname_by_case`, PIB/rank token extraction) and normalized to
  spaces in `normalize_string`. Quotes stay in place; roundtrip preserved.
  Note: a bare rank without a following PIB is still not masked (unchanged
  behavior, independent of quotes).

## [2.6.5] - 2026-06

### Changed
- The combined-unmask-regex fallback (v2.6.4) now logs a `WARNING` when the
  alternation regex fails to compile, instead of silently switching to the
  slow per-mask path

## [2.6.4] - 2026-06

### Performance
- Unmask of non-rank data is now a single alternation-regex pass instead of
  one full-text scan per mask — ~10× faster on large documents
  (278 KB: ~30 s → ~2.8 s). Longer masks take priority over substrings;
  per-mask occurrence counter keeps instance tracking exact. Slow per-mask
  path kept as fallback for masks that break regex compilation

## [2.6.3] - 2026-06

### Fixed
- Lettered sub-items no longer masked as initials: `п. В. Петренко` (item B),
  `ст. А. Кодексу`, `абз. Б. …` etc. — when a service abbreviation
  (`п.`, `пп.`, `ч.`, `ст.`, `абз.`, `гл.`, `розд.`, …) directly precedes an
  initials+surname pattern, the leading letter is treated as a clause marker,
  not a name

## [2.6.2] - 2026-06

### Fixed
- Windows: close log file handlers before `os.unlink()` in tests
  (`PermissionError: [WinError 32]` from held file locks)

## [2.6.1] - 2026-06

### Changed
- `docs/README.md` translated to English; Ukrainian original moved to
  `docs/README_UK.md`; both cross-linked

## [2.6.0] - 2026-06

Release rollup of 2.5.2–2.5.8 (reversible initials, instance tracking fixes,
live `MASK_*` flags, O(n) replacements, threat model docs, stderr passwords).

### Changed
- Version strings synchronized across all file headers (were stuck at 2.5.1)
- Historical "extracted during vX refactoring" phrases pinned to v2.5.0
  so they no longer drift with version bumps

## [2.5.8] - 2026-06

### Performance
- Replacement loops (mask engine, initials phase, both unmask passes) build
  the result via segment join instead of rebuilding the whole string per
  replacement — O(n) instead of O(n²) on large documents

### Fixed
- Mask engine processes items in document order: instance numbers now match
  occurrence order (was reverse — wrong original could be restored when two
  different values masked to the same string)

## [2.5.7] - 2026-06

### Security
- Generated encryption passwords are printed to **stderr** (not stdout) with
  a "shown once" warning — keeps them out of redirected output, pipes and
  CI logs

## [2.5.6] - 2026-06

### Changed
- README updated for the package architecture (`masking/`, `unmasking/`,
  `__main__.py`), initials masking documented
- README: new "Модель загроз та обмеження" section — honest statement that
  this is pseudonymization (partial digit/letter preservation, deterministic
  unsalted hashing, rank shift ±1-2, date shift ±30 days)
- Wrapper docstrings: corrected `python -m` mention (actual invocation is
  `python . mask` / `python . unmask` from the repo root)

## [2.5.5] - 2026-06

### Changed
- `modules/rank_data.py` is now a re-export of the root `rank_data.py`
  (was a full 636-line copy that could silently diverge)

## [2.5.4] - 2026-06

### Fixed
- `data_masking.MASK_*`, `DEBUG_MODE`, `PRESERVE_CASE`, `HASH_ALGORITHM` are
  live again: reads and writes through the wrapper delegate to
  `masking.constants` (after the v2.5.0 refactoring writes were silently
  ignored — broken backward compatibility)

### Changed
- Removed unused imports in `masking/cli.py` (`SelectiveFilter`,
  `apply_filter_to_globals`, `ReMasker`)

## [2.5.3] - 2026-06

### Fixed
- Repeated text dates (`06 жовтня 2025 року` twice in a document) now track
  instances `[1, 2, ...]` — previously only the first occurrence was restored
  by unmask
- Text date masking inside the engine is now deterministic (the internal copy
  of the function never seeded the RNG)

### Changed
- Removed duplicated `_mask_date_text` implementation (~50 lines);
  it is now an alias of `mask_date_text`

## [2.5.2] - 2026-06

### Fixed
- **Initials are now reversible**: masked initials (`Іванов П.А.` etc.) are stored
  in the mapping under new `initials` category — unmask restores them
- Initials regexes no longer match across line breaks (`П.А.\nСлово` false positive)
- Main PIB parser no longer re-masks surnames already masked by the initials
  phase (nested masks broke unmask)
- Initials mapping is written in document order — instance tracking stays
  consistent with occurrence order

### Added
- `tests/test_initials.py` — 27 tests covering all formats and mask→unmask roundtrip
- Version asserts in tests are now dynamic (compare against `masking.constants`)

## [2.5.1] - 2026-04

### Fixed
- Unmask broken for v2.3+ mappings (`check_mapping_version` fell through to v1 logic)
- `_mask_initial` now uses surname as seed context (different PIBs produce different initials)
- `_UA_UPPER` completed with missing letters (Ї, Є, Ґ, Щ, Ч, Ш, Й)

### Changed
- Performance: `EXCLUDE_WORDS` and `RANKS_LIST` cached as `frozenset` for O(1) lookups
- Performance: `normalize_broken_ranks` regex compiled once (lazy cached)

## [2.5.0] - 2026-04

### Changed
- **Refactoring**: split `data_masking.py` (2654 lines) into `masking/` package with 8 modules:
  `constants`, `helpers`, `language`, `context`, `mask_personal`, `mask_military`, `engine`, `cli`
- **Refactoring**: split `unmask_data.py` (1369 lines) into `unmasking/` package with 4 modules:
  `helpers`, `engine`, `io`, `cli`
- Root-level `data_masking.py` and `unmask_data.py` are now thin wrappers with full backward compatibility

### Added
- `__main__.py` — run as `python . mask [args]` or `python . unmask [args]`
- `masking/` package — modular masking implementation
- `unmasking/` package — modular unmasking implementation
- PIB masking with initials: `Іванов П.А.`, `П. Агранов`, `К.П. Іванов`, `Т. А. Сидоренко`, `КОВАЛЕНКО І.В.`

## [2.3.2] - 2026-04

### Fixed
- Rank and PIB masking in lines with section numbering (e.g. `20.1.2.1.`)
- Trailing punctuation (`,`) preserved when extracting PIB words
- CI: release workflow handles existing releases (create or upload)

## [2.3.1] - 2026-03

### Fixed
- Unicode output crash on Windows (PyInstaller cp1252 encoding issue)
- Replaced Cyrillic text in argparse help with English for cross-platform compatibility
- Added PyInstaller runtime hook to force UTF-8 on Windows

### Changed
- CI: replaced softprops/action-gh-release with `gh` CLI
- CI: opted into Node.js 24 for GitHub Actions runners
- Docs: updated copyright year range to 2025-2026

## [2.3.0] - 2026

### Added
- `modules/security.py` — AES-256-GCM encryption/decryption for mapping files
- `modules/config.py` — YAML + ENV + CLI configuration with priority chain (CLI > ENV > YAML > Default)
- `modules/masking_logger.py` — structured logging (JSON + colored console output)
- `modules/selective.py` — `--only` / `--exclude` filters for selective masking
- `modules/re_mask.py` — multi-pass re-masking with chain tracking
- `modules/tools.py` — atomic masking functions for programmatic API usage
- `modules/password_generator.py` — cryptographically secure password generation
- CI/CD: GitHub Actions for linting, testing (Python 3.13, 3.9 compat), and releases
- CI/CD: Windows binary builds via PyInstaller

### Changed
- Complete migration to `modules/` package architecture
- UTF-8 encoding fixes (mojibake prevention)

## [2.2.14] - 2025

### Changed
- Improved code documentation with detailed docstrings
- Added inline comments for complex logic
- Improved block comments for code sections

## [2.2.13] - 2025

### Changed
- Merged `data_masking.py` (v2.2.10) and `data_masking_v2_2_12_fixed.py`
- Preserved all bug fixes from v2.2.12

## [2.2.12] - 2025

### Fixed
- Bug #18: `mask_rank()` did not preserve Title Case for multi-word ranks
  ("Старший Лейтенант" now correctly maps to "Майор" in Title Case)

## [2.2.11] - 2025

### Fixed
- Bug #16: `mask_rank()` did not preserve case when using `.title()`
  ("Капітан" now correctly maps to "Майор" in Title Case)
- Bug #17: `mask_name()` did not apply case for names already in mapping
  ("петро" now correctly maps to "павло" in lowercase)

## [2.2.10] - 2025

### Fixed
- Bug #15: "старшого\nсержанта" was incorrectly masked as "старшого старшого сержанта"
  Added `normalize_broken_ranks()` function to handle line-broken ranks
- Restored full report format and statistics output

## [2.1.16] - 2025

### Added
- Abbreviation whitelist support (ЗСУ, МОУ, ВСУ, etc. are no longer masked)

## [2.0.0] - 2025

### Added
- Instance tracking for all masked values
- Deterministic masking via blake2b hash-based seed generation
- v2.0 mapping file format with per-instance tracking
- Support for Ukrainian military ranks with all grammatical cases (nominative, genitive, dative, instrumental)
- Gender-aware masking (male/female rank forms)
- Case preservation (UPPER, Title, lower)
- Support for "у відставці" / "в запасі" / "на пенсії" suffixes

### Supported data types
- PIB (names, surnames, patronymics) with declension support
- IPN (10-digit tax identification numbers)
- Passports (AA123456) and ID passports (9-digit)
- Military IDs (МТ123456)
- Military ranks (Army, Navy, Legal, Medical services)
- Brigades, military units (в/ч А1234)
- Order numbers (наказ №123)
- BR numbers (75/25/3400/Р)
- Dates (DD.MM.YYYY with ±30 day shift)
