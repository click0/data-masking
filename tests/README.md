# Tests для Data Masking System v2.2.14

## 🧪 Структура тестів

```
tests/
├── __init__.py              # Package init
├── conftest.py              # Pytest fixtures та конфігурація
├── test_helpers.py          # Тести для helper функцій (_apply_original_case)
├── test_patronymic.py       # Тести для маскування по батькові
└── test_case_preservation.py # Тести для збереження регістру
```

## 🚀 Запуск тестів

### Всі тести:
```bash
pytest
```

### З verbose output:
```bash
pytest -v
```

### Конкретний файл:
```bash
pytest tests/test_helpers.py
```

### Конкретний тест:
```bash
pytest tests/test_helpers.py::TestApplyOriginalCase::test_uppercase
```

### По маркерам:
```bash
pytest -m unit           # Тільки unit тести
pytest -m patronymic     # Тільки тести по батькові
pytest -m integration    # Тільки integration тести
```

### З coverage:
```bash
pytest --cov=. --cov-report=html
```

## 📋 Маркери

- `unit` - Unit тести (швидкі, ізольовані)
- `integration` - Integration тести (повільніші, комплексні)
- `patronymic` - Тести маскування по батькові
- `rank` - Тести обробки звань
- `pii` - Тести обробки ПІІ
- `slow` - Повільні тести
- `masking` - Тести маскування
- `unmasking` - Тести unmask

## 🎯 Coverage

Очікуваний coverage після всіх тестів:
- `_apply_original_case()` - 100%
- `mask_patronymic()` - 90%+
- `mask_rank()` (case preservation) - 80%+

## ⚙️ Fixtures

### Доступні fixtures (conftest.py):
- `empty_masking_dict` - Порожній словник маскування
- `sample_masking_dict` - Заповнений приклад
- `instance_counters` - Лічильники instances
- `sample_text_with_pib` - Зразок тексту з ПІБ
- `sample_text_with_rank` - Зразок тексту зі званням

## 📝 Приклад використання

```python
def test_my_function(empty_masking_dict, instance_counters):
    from data_masking import mask_patronymic
    
    result = mask_patronymic("Миколайович", "male", empty_masking_dict, instance_counters)
    
    assert result != "Миколайович"
    assert "patronymic" in empty_masking_dict["mappings"]
```

## 🐛 Troubleshooting

### ImportError: No module named 'data_masking'
**Рішення:** Запускайте pytest з батьківської директорії:
```bash
cd /path/to/project
pytest tests/
```

### KeyError: 'mappings'
**Рішення:** Використовуйте fixture `empty_masking_dict` замість `{}`

### Tests не знаходяться
**Рішення:** Перевірте що:
1. Файли називаються `test_*.py`
2. Функції називаються `test_*`
3. Класи називаються `Test*`
4. `pytest.ini` в корені проекту

## 📊 Статистика тестів

**Всього тестів:** ~30+
- Helper функції: ~10 тестів
- Patronymic: ~15 тестів
- Case preservation: ~8 тестів

**Час виконання:** ~1-2 сек

## 🔄 CI/CD

Для GitHub Actions додайте:
```yaml
- name: Run tests
  run: |
    pip install pytest pytest-cov
    pytest --cov=. --cov-report=xml
```

## 📞 Підтримка

**Issues:** https://github.com/click0/data-masking/issues  
**Author:** Vladyslav V. Prodan
