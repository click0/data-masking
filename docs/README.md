[Українська версія / Ukrainian version](README_UK.md)

# Data Masking & Unmasking Scripts

Scripts for **consistent masking** of sensitive data in military documents with the ability to accurately restore the original.

Current version — see [CHANGELOG.md](../CHANGELOG.md) or `python data_masking.py -V`.

---

## 📋 Project Structure

### Entry Points
- **`data_masking.py`** — data masking (thin wrapper over the `masking/` package)
- **`unmask_data.py`** — unmasking (thin wrapper over the `unmasking/` package)
- **`diagnose_mapping.py`** — diagnostics, mapping comparison and recovery verification
- **`__main__.py`** — run from the repository root: `python . mask [args]` / `python . unmask [args]`

### `masking/` Package (masking core, v2.5.0+)
| Module | Description |
|--------|-------------|
| `constants.py` | `MASK_*` flags, patterns, name dictionaries, metadata (single source of version) |
| `helpers.py` | Seed, mapping, instance tracking, normalization |
| `language.py` | Gender, grammatical case, name declension |
| `context.py` | Recognition of lines containing PIB (Прізвище Ім'я По-батькові), context parsing |
| `mask_personal.py` | IPN, passports, surnames, first names, patronymics |
| `mask_military.py` | Ranks, units, orders, BR, dates |
| `engine.py` | Main engine: context-aware masking of text/JSON, initials |
| `cli.py` | CLI, config, reports, `main()` |

### `unmasking/` Package (unmasking core, v2.5.0+)
| Module | Description |
|--------|-------------|
| `helpers.py` | Instance map, file pair lookup, mapping versions |
| `engine.py` | Text/JSON recovery, re-mask chains |
| `io.py` | Loading mapping (.json/.enc), schema validation |
| `cli.py` | CLI, `main()` |

### Data
- **`rank_data.py`** — UAF ranks (army, navy, medical/legal service) with declensions; `modules/rank_data.py` — re-export

### `modules/` Package (optional features)
| Module | Description |
|--------|-------------|
| `config.py` | YAML + ENV + CLI configuration with priorities (CLI > ENV > YAML > Default) |
| `security.py` | AES-256-GCM encryption/decryption of mapping files |
| `masking_logger.py` | Structured logging (JSON + colored console output) |
| `selective.py` | `--only` / `--exclude` filters for selective masking |
| `re_mask.py` | Chain re-masking (multi-pass) with chain tracking |
| `tools.py` | Atomic masking functions for programmatic use (API) |
| `password_generator.py` | Password generator (ASCII, Cyrillic, custom symbols) |

### Supporting Files
- **`config_example.py`** — configuration example (dataclasses, no external dependencies)

---

## 🚀 Quick Start

### Masking
```bash
python data_masking.py input.txt
```

**Result:**
- `output/masked_input_YYYYMMDD_HHMMSS.txt` — masked text
- `output/mapping_input_YYYYMMDD_HHMMSS.json` — mapping for unmask
- `output/report_input_YYYYMMDD_HHMMSS.txt` — report

### Unmasking

**Automatic mode:**
```bash
python unmask_data.py masked_file.txt
```

**Manual mode:**
```bash
python unmask_data.py masked_file.txt -m mapping_file.json
```

**With encrypted mapping file (v2.3.0+):**
```bash
python unmask_data.py masked_file.txt --map mapping.enc --password mypassword
```

**With configuration file (v2.3.0+):**
```bash
python unmask_data.py -c config.yaml
```

**Result:**
- `result/unmasked_file_YYYYMMDD_HHMMSS.txt` — recovered text

### Diagnostics
```bash
python diagnose_mapping.py mapping1.json mapping2.json   # compare mappings
python diagnose_mapping.py --verify input.txt recovered.txt  # verify recovery
```

---

## 📊 What Gets Masked

### Personal Data
- **PIB (Прізвище Ім'я По-батькові)** — with grammatical case and gender awareness
- **PIB with initials** (v2.5.0+) — `Іванов П.А.`, `П. Агранов`, `К.П. Іванов`, `Т. А. Сидоренко`, `КОВАЛЕНКО І.В.`; initials are preserved in the mapping and restored during unmask
- **Patronymics** — masked while preserving gender and letter case
- **IPN** — 10 digits
- **ID passports** — 9 digits (first 3 + last are fixed, middle 5 are random)
- **Passports** — АА123456, АА №123456
- **Military IDs** — МТ123456, мт-123456, мт №123456

### Military Data
- **Ranks** — all grammatical cases, masculine/feminine forms, with "retired"/"reserve" modifiers
- **Brigades** — "123 окрема механізована бригада"
- **Military units** — "в/ч А1234"
- **Order numbers** — "наказ №123 від 01.01.2025"

### Documents
- **BR numbers** — 75/25/3400/Р, 818/856, 86319/06/1689/Р, 566
- **Dates** — DD.MM.YYYY (±30 days)

### Exceptions
- **Abbreviations** — ЗСУ, МОУ, ВСУ, ДПСУ, НГУ, ДСНС, СБУ, ГУР, ТЦК, СП

---

## 🎯 Features

### Instance Tracking
Each occurrence is tracked individually:
```
Вхід:  "Іванов зустрів Петрова, потім Іванов пішов"
Маска: "Сидоров зустрів Коваля, потім Сидоров пішов"
                ↑ instance 1           ↑ instance 2
Unmask правильно відновить обидва входження
```

### Preserving Grammatical Forms

**Rank declension:**
```
"молодшому сержанту"   → "старшому солдату"   (давальний)
"молодшого сержанта"   → "старшого солдата"   (родовий)
"молодшим сержантом"   → "старшим солдатом"   (орудний)
```

**Name declension:**
```
"Іванову Петру"    → "Сидорову Андрію"    (давальний)
"Іванова Петра"    → "Сидорова Андрія"    (родовий)
"Івановим Петром"  → "Сидоровим Андрієм"  (орудний)
```

**Gender:**
```
"молодшою сержанткою"  → "старшою солдаткою"  (жіночий)
"капітанці"            → "майорці"            (жіночий)
```

**Additional modifiers:**
```
"Солдату у відставці"     → "Рекруту у відставці"        (давальний зберігається!)
"Сержанту в запасі"       → "Старшому солдату в запасі"  (давальний зберігається!)
"Капітану на пенсії"      → "Майору на пенсії"           (давальний зберігається!)
```

### Case Preservation
```
"ІВАНОВ"   → "ПЕТРЕНКО"
"Іванов"   → "Петренко"
"іванов"   → "петренко"
```

### Deterministic Generation

The system generates **identical** mapping files when processing **identical** input data:

```python
# Запуск 1:
"Іванов" → blake2b hash → seed → "Петренко"

# Запуск 2 (той самий файл):
"Іванов" → blake2b hash → seed → "Петренко"  # Той самий результат!
```

**Advantages:**
- One original = one mask (always)
- Results are predictable and reproducible
- You can re-run on the same file and get the same mapping
- Unmask works consistently

**Technical details:**
- Uses `hashlib.blake2b()` for seed generation
- Faker and random are initialized with a deterministic seed

---

## 🔧 Modules v2.3.0

### Mapping File Encryption (`modules/security.py`)

Mapping files can be encrypted with AES-256-GCM:

```bash
# Маскування з шифруванням
python data_masking.py input.txt --encrypt --password mypassword
# Результат: mapping_*.json.enc

# Розмаскування з шифрованим mapping
python unmask_data.py masked.txt --map mapping.enc --password mypassword
```

### Configuration (`modules/config.py`)

Priority: CLI > ENV > config.yaml > Default

```bash
# Використання YAML конфігурації
python data_masking.py input.txt -c config.yaml

# Генерація прикладу конфігурації — див. config_example.py
```

### Selective Masking (`modules/selective.py`)

```bash
# Маскувати тільки ІПН та паспорти
python data_masking.py input.txt --only ipn,passport

# Маскувати все крім дат
python data_masking.py input.txt --exclude dates
```

### Chain Re-masking (`modules/re_mask.py`)

For re-masking already masked files while preserving the full mapping chain:

```python
from modules.re_mask import ReMasker, MappingChain

chain = MappingChain()
remasker = ReMasker(chain=chain, mask_function=my_mask_fn)
```

### Programmatic API (`modules/tools.py`)

Atomic functions for integration into external applications:

```python
from modules.tools import mask_ipn_direct, mask_rank_direct, mask_pib_force

result = mask_ipn_direct("1234567890", masking_dict, instance_counters)
```

### Password Generator (`modules/password_generator.py`)

```python
from modules.password_generator import generate_password

# Стандартний пароль (24 символи)
pwd = generate_password()

# З кирилицею
pwd = generate_password(length=32, include_cyrillic_lower=True)

# CLI
# python -m modules.password_generator --length 32 --cyrillic
```

### Logging (`modules/masking_logger.py`)

Structured logging with JSON and colored console output:

```python
from modules.masking_logger import MaskingLogger, setup_logging

logger = MaskingLogger("masking")
setup_logging(level="DEBUG", json_output=True)
```

---

## ⚙️ Configuration

In `data_masking.py` you can enable/disable categories:

```python
# Алгоритм хешування для детермінованої генерації
HASH_ALGORITHM = 'blake2b'  # blake2b (рекомендовано), md5 (швидкий), sha256 (популярний)

MASK_IPN = True              # ІПН (10 цифр)
MASK_PASSPORT = True         # Паспорти (АА123456) та ID-паспорти (9 цифр)
MASK_MILITARY_ID = True      # Військові квитки
MASK_NAMES = True            # Імена та прізвища
MASK_RANKS = True            # Звання
MASK_BRIGADES = True         # Бригади
MASK_MILITARY_UNITS = True   # Військові частини
MASK_ORDER_NUMBERS = True    # Номери наказів
MASK_BR_NUMBERS = True       # БР номери
MASK_DATES = True            # Дати
```

**Hash algorithm comparison:**

| Algorithm | Speed | Security | Usage |
|-----------|-------|----------|-------|
| blake2b   | ⚡⚡⚡⚡⚡ | ✅ High | Recommended (default) |
| md5       | ⚡⚡⚡⚡⚡ | ⚠️ Low for cryptography | Fastest, sufficient for seed |
| sha1      | ⚡⚡⚡⚡ | ⚠️ Deprecated | Fast, better than md5 |
| sha256    | ⚡⚡⚡ | ✅ High | Popular, Bitcoin |
| sha512    | ⚡⚡ | ✅ Maximum | Slowest |

---

## 📝 Masking Examples

### Example 1: Declensions and additional modifiers
**Input:**
```
Молодшому сержанту у відставці СИЧУ Роману Сергійовичу (Житомирський ОТЦКСП),
звільненому 31.05.2025, який є особою з інвалідністю III групи.
```

**Result:**
```
Старшому солдату у відставці БОЙКО Павлу Сергійовичу (Житомирський ОТЦКСП),
звільненому 15.06.2025, який є особою з інвалідністю III групи.
```

### Example 2: Feminine forms and documents
**Input:**
```
Капітанці медичної служби Коваленко Марії Іванівні, ІПН 1234567890,
ID-паспорт 123456789, видано наказом №75/25/3400/Р від 26.06.2025.
```

**Result:**
```
Майорці медичної служби Петренко Оксані Іванівні, ІПН 9876543210,
ID-паспорт 123947568, видано наказом №59/87/4249/Р від 10.07.2025.
```

### Example 3: Signature format
**Input:**
```
Командир 72 окремої механізованої бригади
полковник                           Сергій ЗАПОРОЖЕЦЬ
```

**Result:**
```
Командир 85 окремої механізованої бригади
підполковник                        Павло ЗАВОДСЬКИЙ
```

### Example 4: Abbreviations are not masked
**Input:**
```
Капітан ЗСУ Іванов Петро Миколайович, військовий квиток МТ123456,
проходив службу у МОУ, нагороджений СБУ за заслуги перед ГУР.
```

**Result:**
```
Майор ЗСУ Сидоров Андрій Миколайович, військовий квиток МТ654321,
проходив службу у МОУ, нагороджений СБУ за заслуги перед ГУР.
```

### Example 5: Multiple PIB in one line
**Input:**
```
Сержанту БОНДАРЕНКО Олегу та молодшому сержанту КОВАЛЕНКО Андрію,
а також рядовому ШЕВЧЕНКО Петру видати по 100 грн.
```

**Result:**
```
Старшому солдату ЗАВОДСЬКИЙ Павлу та молодшому солдату БОЙКО Станіславу,
а також солдату ПЕТРЕНКО Андрію видати по 100 грн.
```

---

## 📝 Mapping File Format

```json
{
  "version": "2.0",
  "mappings": {
    "rank": {
      "молодшому сержанту": {
        "masked_as": "старшому солдату",
        "instances": [1, 3]
      }
    },
    "surname": {
      "іванов": {
        "masked_as": "петренко",
        "instances": [1, 2]
      }
    },
    "passport_id": {
      "123456789": {
        "masked_as": "123947568",
        "instances": [1]
      }
    }
  },
  "instance_tracking": {
    "старшому солдату": 3,
    "петренко": 2,
    "123947568": 1
  }
}
```

---

## 📚 Supported Ranks

### Army (32 ranks)
**Enlisted:** рекрут, рядовий, солдат, старший солдат

**Sergeants:** молодший сержант, сержант, старший сержант, головний сержант, штаб-сержант, майстер-сержант, старший майстер-сержант, головний майстер-сержант

**Officers:** молодший лейтенант, лейтенант, старший лейтенант, капітан, майор, підполковник, полковник

**Generals:** бригадний генерал, генерал-майор, генерал-лейтенант, генерал

### Navy (22 ranks)
**Sailors:** матрос, старший матрос

**Petty Officers:** головний корабельний старшина, головний старшина, старшина 1/2 статті

**Officers:** молодший лейтенант, лейтенант, старший лейтенант, капітан-лейтенант

**Captains:** капітан 3/2/1 рангу

**Admirals:** контр-адмірал, віце-адмірал, адмірал

### Special Services
**Medical:** капітан/майор/підполковник/полковник медичної служби

**Legal:** капітан/майор/підполковник/полковник юстиції

### Supported Grammatical Cases
- **Називний** (nominative): хто? що? — "солдат"
- **Родовий** (genitive): кого? чого? — "солдата"
- **Давальний** (dative): кому? чому? — "солдату"
- **Орудний** (instrumental): ким? чим? — "солдатом"

---

## 🔐 Security

### Recommendations:
1. Store mapping files in a **secure location**
2. **DO NOT** transmit mapping files together with masked data
3. Delete mapping files after work is complete
4. Use different mappings for different documents
5. Use mapping file encryption (v2.3.0+): `--encrypt --password`
6. Unmask is ONLY possible with the mapping file
7. Pass the password via `--password-env VAR_NAME` instead of `--password`
   (command-line arguments are visible in shell history and process lists)

### ⚠️ Threat Model and Limitations

This is **pseudonymization**, not full anonymization. Consider the following:

- **Partial preservation of the original.** IPN retains the first 3 and last digit
  (4 out of 10), passport retains 4 out of 9, long surnames retain the first 3
  and last 5 characters. This is intentional (preserves format and partial context)
  but allows re-identification by brute-forcing against a candidate dictionary.
- **Deterministic generation without a secret.** Masks are derived from the
  blake2b hash of the original without salt/key. Anyone who knows the algorithm
  and has a list of possible originals can match masks without the mapping file.
- **Ranks are shifted by only ±1-2 positions** in the hierarchy — the approximate
  rank of the person remains visible.
- **Dates are shifted by ±30 days** — the time period of events remains recognizable.

**Conclusion:** masked files protect against accidental disclosure and are suitable
for sharing with a limited audience, but are NOT designed for publication against
a motivated adversary with knowledge of the context.

---

## 🛠️ Troubleshooting

### Unmask does not restore correctly
- Check the mapping version (should be v2.0)
- Use the latest script versions

### Ranks are not masked
- Make sure `MASK_RANKS = True`
- Update to the latest version

### Abbreviations are being masked
- Update to v2.1.16+ with whitelist support

### ID passports are not masked
- Make sure `MASK_PASSPORT = True`
- ID passports = 9 digits (not 10 like IPN)

---

## 📦 Usage in Projects

### Git Submodule (recommended)

```bash
# Add as submodule
git submodule add https://github.com/click0/data-masking.git

# Update submodule
git submodule update --remote data-masking

# Use in project
cd data-masking
python data_masking.py ../documents/input.txt
```

### Standalone

```bash
# Clone separately
git clone https://github.com/click0/data-masking.git
cd data-masking
python data_masking.py input.txt
```

---

## 📜 License

BSD 3-Clause "New" or "Revised" License

---

## 👨‍💻 Author

**Vladyslav V. Prodan**
- GitHub: [@click0](https://github.com/click0)
- Phone: +38(099)6053340

---

## 📅 Version

See [CHANGELOG.md](../CHANGELOG.md) for version history and release notes.
