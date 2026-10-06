# Config examples / Приклади конфігурацій

Ready-made configurations for typical scenarios. Each file lists only what
differs from the defaults; every key is explained in
[`config_example.yaml`](../../config_example.yaml).

Готові конфігурації під типові сценарії. У кожному файлі — лише відмінності
від значень за замовчуванням; усі ключі пояснено в
[`config_example.yaml`](../../config_example.yaml).

| File / Файл | Masked / Маскується | Left open / Відкрито | Mapping | Surname prefix |
|---|---|---|---|---|
| *(defaults)* | everything / усе | — | plain `.json` | 3 |
| [`share.yaml`](share.yaml) | people, IDs, ranks, units, brigades / люди, ідентифікатори, звання, в/ч, бригади | dates, order & BR numbers / дати, номери наказів і БР | encrypted `.enc` | 3 |
| [`strict.yaml`](strict.yaml) | everything / усе | — | encrypted `.enc` | 0 (fully synthetic) |
| [`pii.yaml`](pii.yaml) | people, IDs / люди, ідентифікатори | ranks, units, brigades, dates, documents / звання, в/ч, бригади, дати, документи | encrypted `.enc` | 3 |

```bash
data-mask -i input.txt -o output.txt --config docs/config-examples/share.yaml
```

- `--only` / `--exclude` replace the `enable_*` flags for that run —
  do not combine them with `strict.yaml`.
  `--only` / `--exclude` на час запуску замінюють прапорці `enable_*` —
  не поєднуйте їх зі `strict.yaml`.
- Encrypted mappings need `cryptography` (`pip install 'data-masking[full]'`;
  the Windows binaries include it). Password: `$DATA_MASKING_PASSWORD`,
  `--password-env VAR`, or generated and shown once.
- `pii.yaml` leaves unit and brigade numbers open — internal use only.
  `pii.yaml` лишає відкритими номери в/ч і бригад — лише для внутрішнього
  використання.
