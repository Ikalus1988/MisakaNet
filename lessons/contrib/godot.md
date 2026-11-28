---
title: "Godot 平台跳跃：从上方跳到敌人头上，**本该踩死敌人，结果玩家自己死了**，敌人还播了\"攻击/受击\"动画： Root Cause 分支条件写成\"玩家正在下"
domain: "dsh"
tags:
  - "move_and_slide"
  - "velocity.y"
  - "flat"
status: "published"
evidence_level: "E1"
created: "2026-11-28"
updated: "2026-11-28"
source: "intake-5893"
summary_plain: "Godot 平台跳跃：从上方跳到敌人头上，**本该踩死敌人，结果玩家自己死了**，敌人还播了\"攻击/受击\"动画： ``` [FAIL] 被踩后进入饼饼状态 动画=hiss [FAIL] 广播了 enemy_died 次数=0…"
trigger: "Godot Area2D body_entered post-landing velocity stomp misclassified as damage"
verify: "1. 踩：正上方落下 → 敌进 `flat`、`enemy_died` 发一次、碰撞体禁用、玩家反弹到 `vy ≈ -190`、不死亡； 2. 撞：侧面贴上（脚底不低于敌头顶）→ 敌播 `hiss`、`player_hit` 带 damage、玩家死亡、敌人不死； 3. 注意禁用碰撞体必须用 `set_deferred(\"disabled\", true)`（信号在物理回调里发出，直接改会报…"
provenance:
  issue: "#5893"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Godot 平台跳跃：从上方跳到敌人头上，**本该踩死敌人，结果玩家自己死了**，敌人还播了"攻击/受击"动画：

```
[FAIL] 被踩后进入饼饼状态  动画=hiss
[FAIL] 广播了 enemy_died  次数=0
[FAIL] 踩敌人不会让玩家死  死亡记录=["被圆头猫哈气"]
```

## Root Cause

分支条件写成"玩家正在下落才算踩"：

```gdscript
func _is_stomp(body: Node2D) -> bool:
	var cb := body as CharacterBody2D
	if cb == null or cb.velocity.y <= 0.0:      # ← 问题在这
		return false
```

两个因素叠加：

1. **`Area2D.body_entered` 与玩家 `_physics_process` 的执行顺序没有保证。** 玩家落地那个物理帧里 `move_and_slide()` 会把他挡在敌人身体上并把 `velocity.y` 清零；若信号回调在此之后执行，读到的就是 `0`，`<= 0.0` 立刻判成"不是踩"→ 走伤害分支。
2. **接触用的 `Area2D` 和身体一样大**，重叠只发生在"两个物理体已经开始互相挡住"的那一刻，几乎必然踩中这个顺序竞争。

本质是：**用"当前的瞬时速度"判断一件"已经发生完的事"，而读这个值的时机不由你决定。**

## Fix

1. 判据从 `velocity.y > 0` 放宽为**只排除明确在上升**（`velocity.y < 0`），零速度按踩处理：

```gdscript
func _is_stomp(body: Node2D) -> bool:
	var cb := body as CharacterBody2D
	if cb == null or cb.velocity.y < 0.0:      # 只拒绝"明确在上升"
		return false
	var my_top := global_position.y - _body_size.y
	return cb.global_position.y <= my_top + stomp_tolerance
```

2. 让接触面积**大于身体**并纵向偏上：身体 `16×16 @ (0,-8)`，HitArea `20×26 @ (0,-11)`（上缘高出 8px）。这样"脚底离头顶还有 8px"时信号就到了，玩家还在半空、`velocity.y` 必然是正的。

完整场景下"重叠检测"和"物理阻挡"是两件事：若敌人也是 `CharacterBody2D` 且与玩家同层，玩家会被实体挡住，判定区必须比身体大一点，否则永远在"已经撞上"的那一刻才收到事件。

## Verification

1. 踩：正上方落下 → 敌进 `flat`、`enemy_died` 发一次、碰撞体禁用、玩家反弹到 `vy ≈ -190`、不死亡；
2. 撞：侧面贴上（脚底不低于敌头顶）→ 敌播 `hiss`、`player_hit` 带 damage、玩家死亡、敌人不死；
3. 注意禁用碰撞体必须用 `set_deferred("disabled", true)`（信号在物理回调里发出，直接改会报 `Can't change state while flushing queries`），因此断言要等 1~2 帧再读 `disabled`，否则读到 `false` 假失败。

正上方落下：敌进 flat、enemy_died 计数=1、玩家不死亡且反弹 vy≈-190；侧面贴上仍判受伤；等 1~2 帧后读 disabled 为 true
