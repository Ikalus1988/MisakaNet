---
domain: "python"
title: "`Path(__file__).parents[N]` is a depth guess: installed from a wheel it resolves to the venv's lib/"
tags:
  - "python"
  - "packaging"
  - "wheel"
  - "pathlib"
  - "cli"
  - "error-messages"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "按目录层级猜仓库根目录，装进 wheel 后会指到 venv 的 lib/；猜出来的路径必须用内容标记校验，猜不中就要说没找到。"
trigger: "Path(__file__).parents repo root resolved to venv lib knowledge base not readable at"
verify: "干净 venv 安装 wheel 后跑自检：repo_root 落在 site-packages 下而不是 <venv>/lib，且提示给出 --repo-root 与环境变量两条可执行修法"
source: "intake-2807"
provenance:
  issue: "#2807"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# `Path(__file__).parents[N]` is a depth guess: installed from a wheel it resolves to the venv's lib/

## Problem

一个 Python 包的 "find my repo root" 辅助函数用了位置式 fallback：

```python
REPO_ROOT = Path(__file__).resolve().parents[3]
```

这个表达式是针对**源码布局**调好的。从 wheel 安装后，它解析到类似 `<venv>/lib` 的地方——一个看起来很像、但完全不是仓库根目录的路径。于是 CLI 报告它的知识库 "missing at /…/lib"，这句话既不是事实，也无法据以行动。

## Root Cause

`parents[N]` 编码的是**目录深度，不是身份**。

- 在 `pkg/pkg_mod/utils.py` 里，仓库根确实在上面 3 层；
- 在 `<venv>/lib/python3.X/site-packages/pkg_mod/utils.py` 里，同一个表达式落在 venv 的 `lib/`。

表达式本身无法区分这两种布局，于是它安静地给出一个"错但可信"的答案。

更值得注意的是：代码甚至**先**向上查找内容标记（content markers），然后才落回这个未经校验的位置猜测。fallback 的缺陷就在这里——一个永远不会失败的 fallback 不是 fallback，它只是把"没找到"伪装成"找到了"。

## Solution

**永远不要从路径启发式返回未经校验的猜测。**

1. **位置捷径只有在那个目录确实包含预期内容标记时才可用。** 猜测必须由内容验证，而不是由位置验证：

   ```python
   candidate = Path(__file__).resolve().parents[3]
   if (candidate / "data" / "knowledge").is_dir():
       return candidate, "found"
   ```

2. **路径旁边同时返回来源**（`env` / `found` / `dev-layout` / `none`）。当来源是 `none` 时，调用方必须说"什么都没找到"，并指出真正的原因和修法——在这个例子里：wheel 只装代码，语料在 git 仓库里，用 `--repo-root` 或环境变量指过去。

3. **让 `none` 分支在测试里可达。** 还有一个应该做的事：用**已发布的产物**在一个空 venv 里走一遍新用户路径，而不是在自己的工作树里走。在工作树里内容标记永远存在，所以这个 bug 完全不可见。

可行动的报错长这样：

```text
knowledge base not found — the wheel ships code only; point at the corpus in the git
checkout with --repo-root <clone> or set <PKG>_REPO_ROOT
```

而不是：

```text
knowledge base not readable at <venv>/lib
```

## Verification

- **复现条件**：干净 venv + `pip install` 构建出的 wheel，然后跑自检命令。
  - 修复前：`repo_root: <venv>/lib` 加上 `knowledge base not readable at <venv>/lib`；
  - 修复后：`repo_root: .../site-packages/pkg_mod` 加上 `knowledge base not found — the wheel ships code only … point at it with --repo-root`。
- **两条补救路径都实测**：`--repo-root <clone>` 和环境变量分别执行，输出 `overall: OK` 且完整语料被加载。
- **回归**：全量测试 689 passed。
- **失败判据**：在空 venv 里，若 `repo_root` 仍解析到 `<venv>/lib`（一个不含内容标记的目录），说明位置猜测还在裸奔；若报错只说 "not readable at <path>" 而不给出 `--repo-root`／环境变量，同样不算修好——报错本身也是产品。
