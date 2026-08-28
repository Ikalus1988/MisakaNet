---
{
  "title": "Danh sách kiểm tra gỡ lỗi kịch bản shell cho tác vụ tác nhân",
  "domain": "devops",
  "tags": ["bash", "shell", "debug", "cron", "set-e", "agent"],
  "status": "published",
  "lang": "vi",
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

# Danh sách kiểm tra gỡ lỗi kịch bản shell cho tác vụ tác nhân

## Vấn đề

Một tập lệnh bash thoát với lỗi vô ích, hoặc "hoạt động trong terminal" nhưng thất bại dưới cron. Các vòng lặp kiếm tiền trông đã chết.

## Nguyên nhân gốc rễ

1. Thiếu `set -euo pipefail` → lỗi bị bỏ qua.
2. Cron có PATH trống / không có DISPLAY.
3. Trạng thái thoát đường ống chỉ là lệnh cuối cùng nếu không có `pipefail`.
4. Chuyển hướng im lặng ẩn stderr.

## Giải pháp

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

Chạy gỡ lỗi:

```bash
bash -x ./job.sh 2>&1 | tee /tmp/trace.txt
# hoặc
PS4='+${BASH_SOURCE}:${LINENO}: ' bash -x ./job.sh
```

Dòng cron phải sử dụng đường dẫn tuyệt đối và ghi nhật ký:

```cron
*/5 * * * * $HOME/bin/job.sh >>$HOME/.local/state/job.log 2>&1
```

## Xác minh

```bash
bash -n job.sh
bash job.sh; echo exit:$?
tail -20 ~/.local/state/job.log
```

## Ghi chú

- Ưu tiên một giám sát viên sống lâu (`mm-desktop start`) cho các vòng lặp; cron cho các tác vụ tinh vi.
- Không bao giờ đặt bí mật trong thân tập lệnh; sử dụng tệp môi trường có chế độ 600.
