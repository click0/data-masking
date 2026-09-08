# Git hooks (versioned)

Хуки в `.git/hooks/` не версіонуються, тому спільні лежать тут.
Увімкнути для свого клону (один раз):

```bash
git config core.hooksPath .githooks
```

| Хук | Що робить |
|---|---|
| `prepare-commit-msg` | Якщо коміт робиться з сесії Claude Code (змінна `CLAUDECODE`), додає в кінець повідомлення повний блок атрибуції:<br>`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`<br>`Claude-Session: https://claude.ai/code/session_<id>` (з `CLAUDE_CODE_REMOTE_SESSION_ID`)<br>`Generated-With: Claude Code <version>` (з `CLAUDE_CODE_VERSION`).<br>Ідемпотентно; merge/squash не чіпає. Співавтора можна перевизначити: `git config claude.coauthor "Name <email>"`. |

Вимкнути назад: `git config --unset core.hooksPath`.
