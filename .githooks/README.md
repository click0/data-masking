# Git hooks (versioned)

Хуки в `.git/hooks/` не версіонуються, тому спільні лежать тут.
Увімкнути для свого клону (один раз):

```bash
git config core.hooksPath .githooks
```

| Хук | Що робить |
|---|---|
| `prepare-commit-msg` | Якщо коміт робиться з сесії Claude Code (змінна `CLAUDECODE`), дописує в кінець повідомлення блок атрибуції:<br>`Claude-Session: https://claude.ai/code/session_<id>` (з `CLAUDE_CODE_REMOTE_SESSION_ID`)<br>`Generated-With: Claude Code <version>` (з `CLAUDE_CODE_VERSION`).<br>`Co-Authored-By` модель передає сама (`git commit --trailer "Co-Authored-By: Claude <Model> <noreply@anthropic.com>"`), бо в одній сесії коміти можуть робити різні моделі, а назви моделі в оточенні немає. Явний трейлер має пріоритет; без нього — `CLAUDE_COAUTHOR`, потім `git config claude.coauthor`, інакше узагальнене `Claude <noreply@anthropic.com>` з попередженням.<br>Ідемпотентно; merge/squash не чіпає. |

Вимкнути назад: `git config --unset core.hooksPath`.
