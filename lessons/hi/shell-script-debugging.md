---
{
  "title": "एजेंट जॉब के लिए शेल स्क्रिप्ट डीबगिंग चेकलिस्ट",
  "domain": "devops",
  "tags": ["bash", "shell", "debug", "cron", "set-e", "agent"],
  "status": "published",
  "lang": "hi",
  "source": "MisakaNet-i18n",
  "translated_from": "lessons/en/shell-script-debugging.md",
  "created": "2026-08-01",
  "updated": "2026-08-01",
  "confidence": "0.9"
}
---

# एजेंट जॉब के लिए शेल स्क्रिप्ट डीबगिंग चेकलिस्ट

## समस्या

एक बैश स्क्रिप्ट बिना किसी उपयोगी त्रुटि के निकलती है, या "टर्मिनल में काम करती है" लेकिन क्रॉन तहत विफल हो जाती है। आर्न लूप मृत दिखाई देते हैं।

## मूल कारण

1. `set -euo pipefail` गुम है → विफलताएं अनदेखी की जाती हैं।
2. क्रॉन में खाली PATH / कोई DISPLAY नहीं है।
3. पाइपलाइन एक्सिट स्टैटस `pipefail` के बिना केवल आखिरी कमांड है।
4. साइलेंट रीडायरेक्ट stderr को छुपाते हैं।

## समाधान

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

डीबग रन:

```bash
bash -x ./job.sh 2>&1 | tee /tmp/trace.txt
# या
PS4='+${BASH_SOURCE}:${LINENO}: ' bash -x ./job.sh
```

क्रॉन लाइन绝对 पाथ और लॉग का उपयोग करनी चाहिए:

```cron
*/5 * * * * $HOME/bin/job.sh >>$HOME/.local/state/job.log 2>&1
```

## सत्यापन

```bash
bash -n job.sh
bash job.sh; echo exit:$?
tail -20 ~/.local/state/job.log
```

## नोट्स

- लूप के लिए लंबे समय तक चलने वाले सुपरवाइजर (`mm-desktop start`) को प्राथमिकता दें; पतले टास्क के लिए क्रॉन।
- कभी भी स्क्रिप्ट बॉडी में सीक्रेट न रखें; mode-600 env फाइल का उपयोग करें।
