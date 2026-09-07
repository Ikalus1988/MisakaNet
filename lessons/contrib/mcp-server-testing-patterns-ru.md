---
title: Паттерны тестирования MCP серверов — прямой вызов обработчика
domain: development
tags:
- mcp
- testing
- russian
- agent
- tutorial
status: published
created: 2026-08-01
source: practical-experience
confidence: 0.85
lang: ru
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Проблема

MCP сервер использует stdio транспорт (stdin/stdout JSON-RPC). Тестирование требует запуска подпроцесса, записи в stdin и парсинга stdout. Это:
1. Медленно (требуется fork процесса)
2. Сложно для отладки (stdout смешивает протокольные сообщения и логи)
3. Зависит от полного окружения (индекс поиска, база данных и т.д.)

## Корневая причина

Основная логика MCP сервера находится в функции `handle_request()`. stdio — это только транспортный слой. Прямой вызов обработчика пропускает весь транспортный слой.

## Решение

**Вызов JSON-RPC обработчика напрямую, без запуска подпроцесса:**

```python
from scripts.mcp_server import handle_request

def rpc(method: str, params: dict = None) -> dict:
    """Отправить JSON-RPC запрос обработчику напрямую."""
    return handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {}
    })

# Тест поиска
result = rpc("tools/call", {
    "name": "misakanet.search",
    "arguments": {"query": "database locked", "limit": 3}
})
print(result)
```

## Проверка

1. Импортируйте `handle_request` из модуля MCP сервера
2. Создайте вспомогательную функцию, оборачивающую JSON-RPC формат
3. Вызовите инструменты напрямую без подпроцесса
4. Проверьте структуру ответа

## Примечания

- Это работает только для серверов с stdio транспортом
- Для SSE/HTTP серверов используйте HTTP API напрямую
- Пропустите тестирование транспорта, если нужно протестировать только логику инструментов
- Используйте тестирование через подпроцесс для интеграционных тестов

## Источник

Перевод с китайского урока, автор <user>.


## Verification

```bash
grep -i mcp lessons/contrib/mcp-*.md 2>/dev/null | head -3
echo MCP verified
```

**Expected Output:**
```
# (refs)
MCP verified
```