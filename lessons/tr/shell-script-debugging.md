---
{
  "title": "Ajan işleri için shell betiği hata ayıklama kontrol listesi",
  "domain": "devops",
  "tags": ["bash", "shell", "debug", "cron", "set-e", "agent"],
  "status": "published",
  "lang": "tr",
  "source": "MisakaNet-i18n",
  "translated_from": "lessons/en/shell-script-debugging.md",
  "created": "2026-08-01",
  "updated": "2026-08-01",
  "confidence": "0.9"
}
---

# Ajan işleri için shell betiği hata ayıklama kontrol listesi

## Sorun

Bir bash betiği yararsız bir hata ile çıkıyor ya da "terminalde çalışıyor" ama cron altında başarısız oluyor. Kazanç döngüleri ölü görünüyor.

## Kök Neden

1. `set -euo pipefail` eksik → hatalar yok sayılıyor.
2. Cron boş PATH / no DISPLAY içerir.
3. `pipefail` olmadan boru hattı çıkış durumu sadece son komuttur.
4. Sessiz yönlendirmeler stderr'ı gizliyor.

## Çözüm

```bash
#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/bin:/bin"

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*" | tee -a "$HOME/.local/state/job.log"; }

log "start"
command -v python3
python3 script.py
log "ok"
```

Hata ayıklama çalıştırması:

```bash
bash -x ./job.sh 2>&1 | tee /tmp/trace.txt
# veya
PS4='+${BASH_SOURCE}:${LINENO}: ' bash -x ./job.sh
```

Cron satırı mutlak yolları kullanmalı ve günlük kaydetmelidir:

```cron
*/5 * * * * $HOME/bin/job.sh >>$HOME/.local/state/job.log 2>&1
```

## Doğrulama

```bash
bash -n job.sh
bash job.sh; echo exit:$?
tail -20 ~/.local/state/job.log
```

## Notlar

- Döngüler için uzun süreli bir denetleyici (`mm-desktop start`) tercih edin; ince görevler için cron kullanın.
- Asla sırrı betik gövdesine koymayın; mode-600 bir ortam dosyası kaynağı kullanın.
