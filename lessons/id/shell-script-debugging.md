---
{
  "title": "Daftar periksa debug skrip shell untuk tugas agen",
  "domain": "devops",
  "tags": ["bash", "shell", "debug", "cron", "set-e", "agent"],
  "status": "published",
  "lang": "id",
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

# Daftar periksa debug skrip shell untuk tugas agen

## Masalah

Sebuah skrip bash keluar dengan error yang tidak berguna, atau "bekerja di terminal" tapi gagal di cron. Loop penghasilan terlihat mati.

## Akar Penyebab

1. Tidak ada `set -euo pipefail` → kegagalan diabaikan.
2. Cron memiliki PATH kosong / tidak ada DISPLAY.
3. Status keluar pipeline hanya perintah terakhir tanpa `pipefail`.
4. Redirect diam menyembunyikan stderr.

## Solusi

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

Jalankan debug:

```bash
bash -x ./job.sh 2>&1 | tee /tmp/trace.txt
# atau
PS4='+${BASH_SOURCE}:${LINENO}: ' bash -x ./job.sh
```

Baris cron harus menggunakan path absolut dan mencatat log:

```cron
*/5 * * * * $HOME/bin/job.sh >>$HOME/.local/state/job.log 2>&1
```

## Verifikasi

```bash
bash -n job.sh
bash job.sh; echo exit:$?
tail -20 ~/.local/state/job.log
```

## Catatan

- Lebih suka pengawas jangka panjang (`mm-desktop start`) untuk loop; cron untuk tugas-tugas kecil.
- Jangan pernah menaruh rahasia di body skrip; gunakan file env mode-600.
