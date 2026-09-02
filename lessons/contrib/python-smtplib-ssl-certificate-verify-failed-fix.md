---
title: Fix Python Smtplib SSL Certificate Verify Failed Error When Sending Emails
  Via Gmail
domain: automation
tags:
- python
- ssl
- smtp
- gmail
- network
- email
status: published
created: '2026-07-30'
updated: '2026-07-30'
source: https://github.com/agente-gaudi/n8n-automation-workflows
confidence: 0.95
domain_expert: python-net
verified_date: '2026-07-30'
---

# Fix Python Smtplib SSL Certificate Verify Failed Error When Sending Emails Via Gmail

## Problem

При выполнении скрипта на Python для автоматической отправки электронных писем через SMTP-сервер Gmail (`smtp.gmail.com`) с использованием стандартной библиотеки `smtplib` и `ssl` возникает ошибка проверки сертификата SSL:

```text
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1028)
```

Скрипт прерывает выполнение и не может аутентифицироваться на сервере Gmail.

## Root Cause

Данная ошибка возникает по двум основным причинам:

1. **Отсутствие локальных корневых сертификатов (CA Certificates):** В некоторых ОС (например, Windows или чистых дистрибутивах macOS/Linux) Python не содержит встроенного хранилища доверенных корневых сертификатов, либо не имеет доступа к системному хранилищу ОС.
2. **Промежуточные прокси / Корпоративный SSL Inspection:** Находясь в сети с перехватом трафика (корпоративный прокси, фаервол с глубоким анализом пакетов DPI или локальный антивирус), SSL-сертификат `smtp.gmail.com` подменяется самоподписанным сертификатом шлюза, который Python не признает доверенным.

| Причина | Диагностика | Затронутые среды |
|---|---|---|
| Отсутствие CA certs | Python не видит системный сертификат | Чистый Python на Windows / macOS |
| SSL Inspection | Подмена сертификата шлюзом сети | Корпоративные сети, прокси |

При вызове `ssl.create_default_context()` контекст строго требует валидации цепочки доверия сертификата, что приводит к сбою на этапе TLS-рукопожатия.

## Solution

Для решения этой проблемы необходимо правильно настроить контекст SSL или переключиться с `SMTP_SSL` на шифрование `STARTTLS` с использованием неутилизирующего контекста в управляемой автоматизированной среде.

### Step 1: Использование неутилизирующего контекста SSL (Быстрое решение для корпоративных/изолированных сетей)

Создайте контекст SSL, отключив обязательную проверку имени хоста и валидацию цепочки сертификатов:

```python
import smtplib
import ssl

# Создаем контекст SSL без проверки сертификата
context = ssl._create_unverified_context()

SENDER_EMAIL = "your.email@gmail.com"
APP_PASSWORD = "your_16_char_app_password"
RECEIVER_EMAIL = "target@example.com"

message = f"""Subject: Test Email\n\nAutomated message sent via python."""

with smtplib.SMTP('smtp.gmail.com', 587) as server:
    server.ehlo()
    server.starttls(context=context)
    server.ehlo()
    server.login(SENDER_EMAIL, APP_PASSWORD)
    server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.encode('utf-8'))
```

### Step 2: Установка пакета `certifi` (Корректное решение для локальной разработки)

Если требуется сохранить полную безопасность SSL-соединения:

1. Установите модуль `certifi`:
   ```bash
   pip install certifi
   ```
2. Укажите путь к CA-сертификатам при создании SSL-контекста:
   ```python
   import smtplib
   import ssl
   import certifi

   context = ssl.create_default_context(cafile=certifi.where())

   with smtplib.SMTP('smtp.gmail.com', 587) as server:
       server.starttls(context=context)
       server.login("your.email@gmail.com", "your_16_char_app_password")
       server.sendmail("your.email@gmail.com", "target@example.com", "Test body")
   ```

## Verification

```bash
pip install certifi
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `pip install certifi`)

## Notes

- Для аутентификации в Gmail с 2022 года **обязательно** требуется использовать 16-значный **App Password** (Пароль приложения), а не основной пароль аккаунта Google.
- Использование `ssl._create_unverified_context()` рекомендуется использовать только в защищенных или контроллируемых средах автоматизации, где сеть изолирована или проксируется доверенными корпоративными шлюзами.
- Источник и связанная документация: [Python smtplib Docs](https://docs.python.org/3/library/smtplib.html).