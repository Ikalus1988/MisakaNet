---
title: "Alembic Upgrade 失败分层定位与数据库迁移规范"
domain: "devops"
tags:
  - "alembic"
  - "database"
  - "sqlalchemy"
  - "migration"
  - "subprocess"
status: "published"
evidence_level: "E2"
provenance:
  issue: "#1553"
  source: "issue-#1553"
evidence_refs:
  - "issue:#1553"
---

# Alembic Upgrade 失败分层定位与数据库迁移规范

## Problem

在 CI/CD 自动化流水线或本地开发环境中，运行 Python 数据库迁移命令（如 `alembic upgrade head` 或在测试框架中通过 `subprocess.run()` 触发）时，抛出 `subprocess.CalledProcessError: Command '['alembic', 'upgrade', 'head']' returned non-zero exit status 1` 异常。

迁移失败可能发生在以下不同的分层中，需进行快速定位：
1. **连接层 (Connection Layer)**：数据库服务未启动、主机名/端口无法解析、网络超时或 `SQLALCHEMY_DATABASE_URI` 配置错误。
2. **权限层 (Permission Layer)**：数据库用户缺少 `CREATE TABLE`、`ALTER TABLE` 或对 `alembic_version` 表的 `SELECT/INSERT/UPDATE` 权限。
3. **SQL 语法层 (SQL Syntax Layer)**：迁移脚本中的 DDL/DML 语法与具体数据库方言（如 PostgreSQL vs MySQL vs SQLite）不兼容。
4. **数据冲突层 (Data Conflict Layer)**：添加 `NOT NULL` 约束但现有表中存有 NULL 记录，或创建唯一索引时已存在重复数据。
5. **模型漂移与版本分叉层 (Model Drift & Version Branching Layer)**：本地或多分支开发导致 `alembic_version` 中记录的版本号与迁移脚本版本树（heads）出现多头分叉或找不到对应 revision。

## Root Cause

1. **`alembic_version` 与本地模型定义分叉机制**：
   Alembic 依靠数据库中的 `alembic_version` 表存储当前单行版本哈希（`version_num`）。当多名开发者各自基于 `main` 分支拉出特性分支并分别生成新的迁移脚本时，各分支的 `down_revision` 均指向同一个父节点。合并分支后，迁移历史树中出现了两个或多个并行终点（Head），触发 `alembic.util.exc.CommandError: Multiple head revisions are present`。如果数据库已升级至节点 A，而代码库切换到了包含节点 B 的分支，Alembic 也会报出 `Can't locate revision identified by 'xxxx'`。

2. **篡改已应用迁移脚本（Violation of Migration Immutability）导致升级失败**：
   迁移脚本本质上是数据库状态变更的不可逆历史日志。若开发者直接修改或删除了已经合并至 `main` 且已在 CI/测试环境或线上数据库中执行过的旧迁移文件（例如修改了 `a1b2c3d4_old.py` 中的字段名或数据类型）：
   - 已应用该迁移的数据库 `alembic_version` 仍记录着旧 Revision ID，但脚本文件已被篡改或移除；
   - 新加入的开发者或 CI 环境从头跑迁移时，会生成与旧环境不一致的数据库 Schema，导致后续依赖原结构的迁移抛出 SQL 异常；
   - 依赖图断裂或状态校验失败，最终引发 `subprocess.CalledProcessError`。

## Solution

### 1. 三连定位法 (Command Triad Diagnosis)
在终端或自动化诊断脚本中依次运行以下命令：
- **查看当前库记录版本**：
