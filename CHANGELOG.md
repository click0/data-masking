# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
