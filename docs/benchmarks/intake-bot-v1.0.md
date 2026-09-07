# intake-bot v1.0 决策基准（2026-09-07）

> 替代"外部试点"的内部离线基准（外部爬虫流量不足；离线基准可重复、可进 CI）。
> 生成器/运行器：`scripts/gen_intake_benchmark.py`、`scripts/intake_benchmark.py`；
> 数据：`tests/benchmarks/intake_benchmark.json`；CI：`intake-benchmark.yml`（路径触发 + dispatch）。

## 方法
- **corpus 快照**：40 篇真实课程（多域），离线注入（不触网）。
- **hit 样本（44）**：36 篇课程派生（title 实词 + problem 片段 → 报错形态）+ 4 篇真实报错形态（curl SSL / git 401 / pip proxy / smtplib SSL）。期望 hit 且命中 = 源课程或同域/同栈。
- **no-hit（11）**：跨语言（#1529 FP 表）+ 泛化错误，期望 ≠ hit。
- **ignore（8）**：URL/JSON/符号/裸码，期望 ignore。

## 结果（sim=0.45）
| 指标 | 值 |
|---|---|
| hit_precision | **1.00**（fp=0；对照 #1529 前 38% FP） |
| hit_recall | **1.00**（44/44） |
| noise_ignore | **1.00**（8/8） |
| 门禁 | `--check`：precision≥0.85 / recall≥0.90 / noise≥0.90 / fp≤0 |

## 基准驱动的引擎改进（并入 intake_bot.py）
栈门放宽为"仅排除**明确不同栈**的课程"——无栈通用课程不再被误滤（同课强词面仍命中）；跨栈误配仍被挡。

## 局限
- hit 主体为课程派生（测决策逻辑，非检索——检索归 #1527）；真实形态 4 条补充。
- 词表驱动栈识别；消费方遵守 suggest-only。
- 真实流量佐证由 `ci-lesson-search`（v1.0 化）挂机观察。
