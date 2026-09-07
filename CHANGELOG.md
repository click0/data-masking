# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
