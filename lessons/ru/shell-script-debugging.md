---
{
  "title": "Контрольный список отладки shell-скриптов для задач агентов",
  "domain": "devops",
  "tags": ["bash", "shell", "debug", "cron", "set-e", "agent"],
  "status": "published",
  "lang": "ru",
  "source": "MisakaNet-i18n",
  "translated_from": "lessons/en/shell-script-debugging.md",
  "created": "2026-08-01",
  "updated": "2026-08-01",
  "confidence": "0.9"
}
provenance:
  source: "external"
  contributor: "Unknown"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

# Контрольный список отладки shell-скриптов для задач агентов

## Проблема

Bash-скрипт завершается без полезной ошибки, или «работает в терминале», но падает под cron. Циклы заработка выглядят мертвыми.

## Коренная причина

1. Отсутствует `set -euo pipefail` → ошибки игнорируются.
2. В cron пустой PATH и нет DISPLAY.
3. Статус выхода конвейера — только последняя команда без `pipefail`.
4. Тихие редиректы скрывают stderr.

## Решение

```bash
#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/bin:/bin"
mkdir -p "$HOME/.local/state"

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*" | tee -a "$HOME/.local/state/job.log"; }

log "start"
command -v python3
python3 script.py
log "ok"
```

Запуск отладки:

```bash
bash -x ./job.sh 2>&1 | tee /tmp/trace.txt
# или
PS4='+${BASH_SOURCE}:${LINENO}: ' bash -x ./job.sh
```

Строка cron должна использовать абсолютные пути и вести журнал:

```cron
*/5 * * * * $HOME/bin/job.sh >>$HOME/.local/state/job.log 2>&1
```

## Проверка

```bash
bash -n job.sh
bash job.sh; echo exit:$?
tail -20 ~/.local/state/job.log
```

## Замечания

- Для долгих циклов предпочитайте долгоживущего супервайзера (`mm-desktop start`); cron — для тонких снайперов.
- Никогда не храните секреты в теле скрипта; используйте env-файл с правами 600.
