---
{
  "title": "Fatal-guard CLI: harden entry point with --help, --version, exit codes",
  "domain": "devops",
  "tags": ["fatal-guard", "cli", "harden", "exit-codes"],
  "status": "published",
  "evidence_level": "E2",
  "source": "closed-pr-1023",
  "created": "2026-08-22"
}
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

Fatal-guard CLI 缺少 `--help`、`--version` 以及规范的退出码支持。这导致以下具体问题：

- **CI/CD 流水线无法区分失败类型**：所有错误都返回相同的非零退出码，使得自动化脚本无法判断是配置错误、超时还是真正的守护失败。
- **用户体验差**：新用户运行工具时没有任何使用说明，必须查阅外部文档才能了解参数格式。
- **不符合 Unix 惯例**：标准 Unix 工具均支持 `--help` 和 `--version`，缺少这些标志会让工具显得不成熟，也会破坏与脚本生态的兼容性（如 `--version` 被包管理器和部署脚本广泛调用）。
- **超时行为不可控**：没有 `--timeout` 参数时，工具可能无限阻塞，导致 CI job 挂起。

## Solution

添加标准 Unix CLI 约定：`--help`、`--version`、`--timeout`，以及规范退出码（0/1/2/3）。

### 退出码定义

| 退出码 | 含义 |
|--------|------|
| `0` | 成功，所有守护进程健康 |
| `1` | 守护进程失败（业务级错误） |
| `2` | 参数错误或用法错误 |
| `3` | 超时，守护进程未在规定时间内响应 |

### 代码示例

**使用 `argparse` 实现标准 CLI 入口（Python）：**

```python
import argparse
import sys

__version__ = "1.4.2"

def build_parser():
    parser = argparse.ArgumentParser(
        prog="fatal-guard",
        description="Monitor and guard critical processes against fatal failures.",
        epilog="Exit codes: 0=success, 1=guard failure, 2=usage error, 3=timeout",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        metavar="SECONDS",
        help="Maximum seconds to wait for a guarded process to respond (default: 30)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="/etc/fatal-guard/config.yaml",
        metavar="FILE",
        help="Path to configuration file",
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Target process name or PID to guard",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.target is None:
        parser.print_help(sys.stderr)
        sys.exit(2)

    try:
        result = run_guard(args.target, timeout=args.timeout, config=args.config)
    except TimeoutError:
        print(f"fatal-guard: timed out after {args.timeout}s", file=sys.stderr)
        sys.exit(3)
    except GuardFailure as e:
        print(f"fatal-guard: guard failure: {e}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
```

**在 Shell 脚本中利用退出码进行分支处理：**

```bash
#!/usr/bin/env bash
fatal-guard --timeout 60 my-service
EXIT_CODE=$?

case $EXIT_CODE in
  0) echo "All guards passed." ;;
  1) echo "ERROR: Guard failure detected. Check service logs."; notify_oncall ;;
  2) echo "ERROR: Bad arguments passed to fatal-guard."; exit 2 ;;
  3) echo "ERROR: fatal-guard timed out. Service may be hung."; restart_service ;;
  *) echo "ERROR: Unknown exit code $EXIT_CODE"; exit 1 ;;
esac
```

**验证 `--version` 输出格式（用于包管理器集成）：**

```bash
# 确保版本号符合 semver 格式
fatal-guard --version | grep -E '^fatal-guard [0-9]+\.[0-9]+\.[0-9]+$'
```

## Key Points

- 退出码帮助 CI/CD 流水线精确检测失败类型，避免误报或漏报
- `--help` 和 `--version` 是所有用户的基本预期，也是 Unix 工具的最低标准
- `--timeout` 防止 CI job 因守护进程无响应而无限挂起
- 使用 `argparse` 可自动生成格式规范的帮助文本，减少文档维护成本
- 退出码应在文档和 `--help` 的 epilog 中明确列出，方便脚本作者查阅

## Verification

```bash
echo "Lesson: Fatal-guard CLI: harden entry point with --help, -"
wc -l lessons/contrib/fatal-guard-cli-hardening.md
```

**Expected Output:**
```
Lesson: Fatal-guard CLI: harden entry point with --help, -
# (line count)
```
