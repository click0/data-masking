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
