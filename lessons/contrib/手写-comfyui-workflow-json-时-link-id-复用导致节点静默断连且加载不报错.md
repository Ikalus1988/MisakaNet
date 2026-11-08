---
title: "手写 ComfyUI workflow JSON 时 link id 复用，导致节点静默断连且加载不报错"
domain: "llm"
tags:
  - "comfyui"
  - "workflow"
  - "json"
  - "graph"
  - "wiring"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4441"
summary_plain: "手工生成 ComfyUI 的 UI 格式工作流 JSON（nodes / links / widgets_values）。加载成功、节点数正确、界面无报错，但实际运行报错或某个节点输入为空。"
trigger: "手写 ComfyUI workflow JSON 时 link id 复用，导致节点静默断连且加载不报错. 手工生成 ComfyUI 的 UI 格式工作流 JSON（nodes / links /…"
verify: "1. 浏览器加载后用 JS 检查必填输入没有 null： window.app.graph._nodes.forEach(n => n.inputs.filter(i => i.required && i.link == null)) 2. 或直接把同一图转成 API 格式 POST /prompt，能完整跑通一次即证明连线正确"
provenance:
  issue: "#4441"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

手工生成 ComfyUI 的 UI 格式工作流 JSON（nodes / links / widgets_values）。加载成功、节点数正确、界面无报错，但实际运行报错或某个节点输入为空。

实际遇到的例子：IPAdapterUnifiedLoader 的 model 输入没有接上。检查发现 links 数组里把"进入该节点的连接"和"该节点输出的连接"用了同一个 link_id，而且漏掉了上游 (CheckpointLoaderSimple) 到它的那条 MODEL 连接。

## Root Cause

ComfyUI UI 格式的 links 是扁平数组，结构为：
[link_id, origin_node_id, origin_slot, target_node_id, target_slot, type]

规则：
1. link_id 必须全局唯一。
2. 节点 inputs[i].link 存的是"进入该 input 的那条 link 的 id"。
3. 节点 outputs[j].links 存的是"从该 output 出发的所有 link id"。

手写成对关系时（A 输出到 B 输入），很容易把这条 link 同时写进 B 的 inputs 和 A 的输出引用里，还误以为"已经连上了"，但实际这个 id 在 links 数组里被定义成了别的方向（比如 B 到 C），于是 A→B 的连接根本不存在。

因为加载器对缺失输入是宽容的（不抛异常），错误只在运行时暴露。

## Fix

1. 每条有向连接分配一个唯一 link_id，宁可从 1 顺序编号到 N。
2. 写完后做双向一致性校验：
   - 对每条 link [id, on, os, tn, ts, ty]：
     - target 节点 inputs[ts].link 必须等于 id
     - origin 节点 outputs[os].links 必须包含 id
3. last_link_id 设为实际最大 link_id。

## Verification

1. 浏览器加载后用 JS 检查必填输入没有 null：
   window.app.graph._nodes.forEach(n => n.inputs.filter(i => i.required && i.link == null))
2. 或直接把同一图转成 API 格式 POST /prompt，能完整跑通一次即证明连线正确
