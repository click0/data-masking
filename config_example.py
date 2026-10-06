#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Приклад конфігурації data-masking v3 у форматі Python (без залежностей).

Альтернатива YAML для середовищ без pyyaml: скопіюйте цей файл як
``config.py`` у директорію, з якої запускаєте програму — завантажувач
підхопить словник ``CONFIG``. Якщо є config.yaml (у тій самій директорії
або через --config), config.py ігнорується ЦІЛКОМ. Змінні оточення
DATA_MASKING_* і прапорці CLI перекривають обидва.

Тут лише ключі, які програма справді читає; значення — за замовчуванням.
Пояснення кожного ключа — config_example.yaml; готові набори під сценарії
(share / strict / pii) — docs/config-examples/.

    python config_example.py      # показати конфігурацію

Author: Vladyslav V. Prodan · github.com/click0
License: BSD 3-Clause
"""

CONFIG = {
    # Що маскувати
    "masking_rules": {
        "enable_names": True,          # прізвища, імена, по батькові, ініціали
        "enable_ipn": True,            # ІПН / РНОКПП
        "enable_passport": True,       # паспорт / ID-картка
        "enable_military_id": True,    # військовий квиток
        "enable_ranks": True,          # звання
        "enable_units": True,          # військові частини
        "enable_brigades": True,       # номери бригад
        "enable_orders": True,         # номери наказів
        "enable_br_numbers": True,     # номери БР
        "enable_dates": True,          # дати (цифрами і текстом)
        # Перші літери оригінального прізвища в масці (0 = повністю синтетична)
        "surname_prefix_length": 3,
    },
    # Вигляд масок і детермінізм
    "system": {
        "preserve_case": True,
        "faker_locale": "uk_UA",
        "hash_algorithm": "blake2b",   # не змінювати посеред пачки документів
        "debug_mode": False,
    },
    # Захист mapping-файлу
    "security": {
        "encrypt_output": False,       # True = те саме, що --encrypt (лише .enc)
        "password_length": 24,         # довжина згенерованого пароля
    },
    "validation": {
        "max_input_size_mb": 100,
    },
    "logging": {
        "level": "INFO",
        "file": None,                  # None = лише консоль
    },
}


if __name__ == "__main__":
    for section, values in CONFIG.items():
        print(f"{section}:")
        for key, value in values.items():
            print(f"  {key}: {value!r}")
