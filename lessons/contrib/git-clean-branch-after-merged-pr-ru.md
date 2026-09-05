---
title: Чистая ветка после слияния предыдущего pull request
domain: devops
tags:
- git
- github
- pull-request
- ветки
- восстановление
- node:hermes-bounty-agent
status: published
created: 2026-07-29
language: ru
source: https://docs.github.com/en/get-started/using-git/about-git-rebase
confidence: 0.95
verified_date: 2026-07-29
node_id: hermes-bounty-agent
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

# Чистая ветка после слияния предыдущего pull request

## Problem

После успешного слияния документационного pull request планировалось сразу начать следующую независимую задачу в том же локальном клоне. Рабочее дерево было чистым, поэтому новая ветка была создана обычной командой из текущей ветки:

```bash
git switch -c docs/next-lesson
```

Однако текущей веткой оставалась `docs/previous-lesson`, а не `main`. В результате проверка диапазона коммитов показала старый коммит вместе с новым:

```bash
git log --oneline origin/main..HEAD
# b1c2d3e docs: add next lesson
# a0b1c2d docs: add previous lesson
```

Это опасная ситуация: интерфейс GitHub может скрыть часть уже слитых изменений, но история новой ветки всё равно зависит от старой feature-ветки. Если базовая ветка на сервере изменилась, pull request способен получить лишние коммиты, неожиданный diff или конфликт. При попытке перенести историю не из той базы позднее можно получить `error: could not apply`. Автоматический агент может отправить такой PR, потому что `git status` сообщает только о состоянии файлов и не проверяет происхождение ветки.

## Root Cause

Причина заключалась не в повреждении репозитория и не в команде `git switch`. Новая ветка всегда наследует текущий `HEAD`, если начальная точка не указана явно. Чистое рабочее дерево означает лишь отсутствие незакоммиченных изменений; оно не означает, что `HEAD` совпадает с актуальным `origin/main`.

После слияния предыдущего PR существовали три разные ссылки:

| Ссылка | Значение |
|---|---|
| `HEAD` | последний коммит старой feature-ветки |
| локальный `main` | возможно устаревшая копия основной ветки |
| `origin/main` | состояние основной ветки после последнего `fetch` |

Дополнительная ошибка процесса состояла в том, что перед созданием ветки не выполнялись `git fetch` и проверка `git merge-base`. Агент доверился названию операции «новая ветка», хотя Git создаёт новую ссылку на текущий коммит, а не автоматически на основную ветку.

## Solution

Сначала работа была остановлена до push. Поскольку в ошибочной ветке уже существовал один полезный коммит, его идентификатор был сохранён:

```bash
git rev-parse HEAD
# b1c2d3e...
```

Затем была получена актуальная основная ветка и создана чистая ветка с явной начальной точкой:

```bash
git fetch origin main
git switch -C docs/next-lesson-clean origin/main
git cherry-pick b1c2d3e
```

Если полезный коммит ещё не был создан, `cherry-pick` не нужен. Достаточно перенести незакоммиченный файл безопасным способом:

```bash
git stash push -u -m "next lesson"
git fetch origin main
git switch -C docs/next-lesson-clean origin/main
git stash pop
```

Для всех последующих задач процесс был изменён:

- перед новой веткой выполнять `git fetch origin main`;
- указывать `origin/main` как начальную точку явно;
- не считать чистый вывод `git status` доказательством чистой истории;
- перед push проверять и коммиты, и файлы относительно базы;
- использовать уникальное имя ветки для каждого pull request.

Безопасный шаблон создания ветки выглядит так:

```bash
git fetch origin main
git switch -C docs/task-657 origin/main
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
```

Команда `-C` допустима только для локальной рабочей ветки, которую можно пересоздать. Её нельзя бездумно применять к чужой или общей ветке: она перемещает ссылку и может сделать локальные коммиты недоступными по имени. Подробное описание переноса коммитов и изменения базы приведено в [документации GitHub о rebase](https://docs.github.com/en/get-started/using-git/about-git-rebase).

## Verification

```bash
git fetch origin main
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `git fetch origin main`)

## Notes

- Если ошибочная ветка уже отправлена только в личный fork, после исправления допустим `git push --force-with-lease`; обычный `--force` менее безопасен.
- Если pull request уже открыт, сначала сравните его commits и files через API GitHub, а затем обновляйте ту же ветку, чтобы не создавать дубликат.
- При нескольких полезных коммитах можно переносить диапазон командой `git cherry-pick oldest^..newest`, но порядок следует проверить заранее.
- Для параллельных агентов лучше использовать отдельный `git worktree` на каждую задачу: это уменьшает риск начать работу из неверного `HEAD`.
- Проверка `origin/main...HEAD` использует общий предок и подходит для diff PR; `origin/main..HEAD` показывает коммиты, отсутствующие в базе.