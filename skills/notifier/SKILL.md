---
name: notifier
description: Send a short Telegram notification when a long-running task finishes. Trigger after a long build, deploy, test run, batch processing, training, sync, large refactor, or anything else the user has been waiting on. Also trigger on explicit phrases like "notify me when done", "ping me when finished", "let me know when ready".
---

# Notifier

Sends a one-line Telegram message via Bot API.

## Usage

Run the script with the message as the first argument:

```bash
bash <skill-dir>/notify.sh "Build finished — 3m 12s"
```

The script reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from `<skill-dir>/.env`. If the env file is missing values it exits with an error.

## Message guidelines

- One short line, plain text.
- Include what finished and the elapsed time when known.
- Do not include secrets, full file paths, or large output.
