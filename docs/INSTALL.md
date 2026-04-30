# Installation

## Python (source)

### Requirements

- Python 3.9+
- pip

### Install

```bash
git clone https://github.com/click0/data-masking.git
cd data-masking
pip install -r requirements.txt
```

### Run

```bash
python data_masking.py -i input.txt
python unmask_data.py masked.txt --map mapping.json
python diagnose_mapping.py
```

### Optional: encrypted mapping files

```bash
pip install cryptography
python data_masking.py -i input.txt --encrypt --password mypassword
python unmask_data.py masked.txt --map mapping.enc --password mypassword
```

### Optional: YAML configuration

```bash
pip install pyyaml
python data_masking.py --init-config        # generate config.yaml template
python data_masking.py -i input.txt -c config.yaml
```

---

## Windows (standalone, no Python needed)

Download `data-masking-VERSION-windows-x64.zip` from the [Releases](https://github.com/click0/data-masking/releases) page.

Extract and run:

```
data_masking.exe -i input.txt
unmask_data.exe masked.txt --map mapping.json
diagnose_mapping.exe
```

### Building Windows binaries locally

Requirements: Python 3.9+, pip, PyInstaller.

```bash
pip install -r requirements.txt
pip install pyinstaller
```

#### Release build (single-file, optimized)

```bash
pyinstaller --onefile --noconfirm --clean \
  --runtime-hook=pyinstaller_utf8_hook.py \
  --collect-all=faker \
  --collect-all=cryptography \
  --hidden-import=rank_data \
  --hidden-import=masking --hidden-import=masking.constants \
  --hidden-import=masking.helpers --hidden-import=masking.language \
  --hidden-import=masking.context --hidden-import=masking.mask_personal \
  --hidden-import=masking.mask_military --hidden-import=masking.engine \
  --hidden-import=masking.cli \
  --hidden-import=modules --hidden-import=modules.config \
  --hidden-import=modules.security --hidden-import=modules.masking_logger \
  --hidden-import=modules.selective --hidden-import=modules.re_mask \
  --hidden-import=modules.password_generator \
  --hidden-import=yaml --hidden-import=_cffi_backend \
  --add-data='rank_data.py;.' \
  --name data_masking \
  data_masking.py

pyinstaller --onefile --noconfirm --clean \
  --runtime-hook=pyinstaller_utf8_hook.py \
  --collect-all=cryptography \
  --hidden-import=rank_data \
  --hidden-import=unmasking --hidden-import=unmasking.helpers \
  --hidden-import=unmasking.engine --hidden-import=unmasking.io \
  --hidden-import=unmasking.cli \
  --hidden-import=modules --hidden-import=modules.config \
  --hidden-import=modules.security --hidden-import=modules.masking_logger \
  --hidden-import=modules.re_mask --hidden-import=modules.rank_data \
  --hidden-import=yaml --hidden-import=_cffi_backend \
  --add-data='rank_data.py;.' \
  --name unmask_data \
  unmask_data.py
```

#### Debug build (with console output and debug symbols)

Adds `--debug all` for verbose bootloader output, `--log-level DEBUG` for
PyInstaller analysis log, and keeps the build directory for inspection.

```bash
pyinstaller --onefile --noconfirm --clean \
  --debug all --log-level DEBUG \
  --runtime-hook=pyinstaller_utf8_hook.py \
  --collect-all=faker \
  --collect-all=cryptography \
  --hidden-import=rank_data \
  --hidden-import=masking --hidden-import=masking.constants \
  --hidden-import=masking.helpers --hidden-import=masking.language \
  --hidden-import=masking.context --hidden-import=masking.mask_personal \
  --hidden-import=masking.mask_military --hidden-import=masking.engine \
  --hidden-import=masking.cli \
  --hidden-import=modules --hidden-import=modules.config \
  --hidden-import=modules.security --hidden-import=modules.masking_logger \
  --hidden-import=modules.selective --hidden-import=modules.re_mask \
  --hidden-import=modules.password_generator \
  --hidden-import=yaml --hidden-import=_cffi_backend \
  --add-data='rank_data.py;.' \
  --name data_masking_debug \
  data_masking.py

pyinstaller --onefile --noconfirm --clean \
  --debug all --log-level DEBUG \
  --runtime-hook=pyinstaller_utf8_hook.py \
  --collect-all=cryptography \
  --hidden-import=rank_data \
  --hidden-import=unmasking --hidden-import=unmasking.helpers \
  --hidden-import=unmasking.engine --hidden-import=unmasking.io \
  --hidden-import=unmasking.cli \
  --hidden-import=modules --hidden-import=modules.config \
  --hidden-import=modules.security --hidden-import=modules.masking_logger \
  --hidden-import=modules.re_mask --hidden-import=modules.rank_data \
  --hidden-import=yaml --hidden-import=_cffi_backend \
  --add-data='rank_data.py;.' \
  --name unmask_data_debug \
  unmask_data.py
```

Debug binaries print import tracebacks and module resolution details at
startup. The `build/` directory contains the analysis results
(`data_masking_debug.toc`, `.pyz` contents list).

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| [faker](https://pypi.org/project/Faker/) | >=20.0.0 | Ukrainian name generation |
| [cryptography](https://pypi.org/project/cryptography/) | >=41.0.0 | AES-256-GCM encryption (optional) |
| [pyyaml](https://pypi.org/project/PyYAML/) | >=6.0 | YAML configuration (optional) |

### Dev dependencies

```bash
pip install -r requirements-dev.txt
```

| Package | Purpose |
|---------|---------|
| pytest | Testing |
| pytest-cov | Coverage |
| pytest-timeout | Test timeout |

---

## Git Submodule

```bash
git submodule add https://github.com/click0/data-masking.git
git submodule update --remote data-masking
```
