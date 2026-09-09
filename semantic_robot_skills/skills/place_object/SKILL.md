---
name: place-object
description: 将已验证持有的物体放到目标槽位并独立验证稳定性
category: robot_skill
version: 0.4.42
runtime:
  api_version: 1
  python: ">=3.11"
  entrypoint: scripts.skill:run
  stop_entrypoint: scripts.skill:on_stop
  input_model: scripts.models:PlaceObjectInput
  state_model: scripts.models:PlaceObjectRunState
  result_model: scripts.models:PlacedObjectState
  controllers:
    placement: scripts.controller:PlacementController
required_actions:
  - { type: sensor.capture_rgbd, schema_version: 2 }
  - { type: robot.get_state, schema_version: 2 }
  - { type: robot.verify_tool_load, schema_version: 2 }
  - { type: perception.locate_object, schema_version: 2 }
  - { type: perception.observe_placement_target, schema_version: 2 }
  - { type: motion.move_end_effector, schema_version: 2 }
  - { type: gripper.release, schema_version: 2 }
  - { type: perception.verify_placement, schema_version: 2 }
  - { type: motion.move_to_posture, schema_version: 2 }
stop_actions:
  - { type: gripper.hold_object, schema_version: 2 }
debug_input:
  object_ref: tote-large-smoke
  target:
    target_ref: pallet-b-slot-r1-c1
    pose_hint: null
    extent_hint_m: [0.56, 0.36, 0.02]
    category_hint: placement_slot
    stability_duration_ms: 1000
---

# 放置物体

这是拆码垛示例中的放置 Robot Skill。它演示 SubTask Goal、Robot Skill Stage、
Placement Controller、Pilot Action Runtime 和 Agent 决策之间的边界，不是某一台
机器人的固定动作脚本。

## Stage 图片证据

关键 Stage 入口及最终完成点使用已有 `sensor.capture_rgbd` 只读能力，各采一帧 RGB；
同一 Execution/Stage/采集点使用稳定 Action key，恢复或局部重试不重复拍摄。
使用 R1 Pro 两种 Robot Profile 声明的通用 `camera.rgb`（不依赖 layout），不采 Depth。
当前 SkillContext 不暴露传感器目录，因此此型号默认值不从地图、Prompt 或宿主机路径推测。
采集失败或 Pilot 未导入图片时上报 `stage.evidence_unavailable`，不改变动作完成判断；
retreat 与停止入口不插入采集。图片的真实 source/observed_at 随 Observation 保留，
由 Pilot 原有 Artifact 链路上传；Server 是否可展示以同步状态为准。
图片仅作执行证据，不代替工具承载、到达或稳定性等独立物理验证。

## 整体期望

成功时必须同时满足：

- 输入物体在开始执行时仍由当前机器人和两个实时发现的工具稳定持有。
- 物体最终处于 PlacementTarget 指定的目标和容差范围内。
- 物体经过目标要求的稳定时间窗口后仍保持稳定。
- 两个工具为空。
- Robot 已恢复 Profile 中的 `travel` 行走姿态。
- 完成结论来自释放和撤离后的独立观测，而不是 release 命令的返回值。

成功输出使用本 Skill 定义的 `PlacedObjectState` JSON。工具调用成功、单侧工具
张开或 Controller 结束都不能单独代表 Skill 完成。

## 输入

- `object_ref`：要从当前 Robot 实时持物状态中复核的业务对象。
- PlacementTarget：Robot Agent 给出的目标、可选位姿提示与稳定
  时间。Semantic Map 只提供规划参考；Skill 开始后由感知 Ability 重新观测槽位，
  不按 Map revision 拒绝实时物理执行。

目标位姿只能来自带 revision 的槽位观测。旧模板中的固定 x/y/z、固定躯干姿态、
宿主机图片路径和 y-3 等流程约定都不进入语义输入。

### 可执行输入

调用方不复制前序 Skill 结果：

```json
{
  "object_ref": "tote-large-smoke",
  "target": {
    "target_ref": "pallet-b-slot-r1-c1",
    "pose_hint": null,
    "extent_hint_m": [0.56, 0.36, 0.02],
    "category_hint": "placement_slot",
    "stability_duration_ms": 1000
  }
}
```

## Stage

| Stage | 期望状态 | Controller / Pilot 行为 |
| --- | --- | --- |
| verify_held_object | 当前机器人仍稳定持有同一物体 | 组合实时Robot状态、工具承载验证和物体观测；Controller复核身份 |
| observe_target_slot | 目标槽位空闲、可达且观测新鲜 | 使用已有观测或请求感知刷新 |
| plan_approach | 形成当前观测版本的短计划 | Placement Controller 沿观测接近向量生成 preplace、release、retreat；密集列只有一侧退出净空不足时，额外生成临时支撑位和厘米级推入动作 |
| approach | 末端到达释放位且未违反约束 | Pilot 执行短计划；受阻时刷新观测并有限重规划 |
| release | 两个工具逐侧释放且逐次收到正式状态证据 | 净空充足时沿用逐侧释放；密集列先让支撑面承重，撤出受阻侧，再由另一侧短推到最终位并释放；不重放状态未知的释放 |
| retreat | 机器人离开物体验证区域 | 只撤回仍在目标附近的工具，再沿已批准撤离路点有限重试 |
| verify_stability | 物体稳定、在容差内且两个工具为空 | 由独立感知源在稳定窗口后验证 |
| restore_travel_posture | 放置结果不再变化且Robot恢复行走姿态 | 调用 Profile 命名姿态 `travel`；失败只请求恢复姿态，不重新抓取 |

这些 Stage 是 Skill 内部执行状态，不会被提升成新的 Workflow、Task 或 SubTask；
每个 Stage 只产生当前所需的少量 Action。Robot Agent 看到的 SubTask Goal 仍是
“把某物体稳定放到某目标”。

## 局部恢复与 Agent 决策

Controller 可以在当前 SubTask Goal 和约束内：

- 刷新过期或被占用的目标槽位观测。
- 因临时阻塞重新生成接近短计划。
- 沿同一安全撤离路点有限重试。
- 在稳定时间窗口后有限复核。

以下情况停止本地推进并请求 Robot Agent：

- 局部恢复预算耗尽。
- 需要更换目标、物体、Robot Skill 或扩大运动边界。
- 释放后无法撤离。
- 独立稳定性验证持续失败。

Agent 返回类型化决定。已经释放的物体不能通过“重试 Action”隐式再次执行释放。
释放物理状态未知时，本次 Skill 直接形成可解释失败；Robot Agent 应创建新的复核或
恢复 SubTask，而不是修改本次 Skill 的 Stage 继续运动。

## 停止

on_stop 通过专用 safe-stop Ability 停止运动并保持当前双工具状态：

- 释放前停止：输出 object_held_at_safe_stop。
- 释放后、独立验证前停止：输出 object_released_but_not_verified，并要求介入。
- 无法确认停止：输出 physical_state_unknown。

停止不会把未验证的物体标记为 PlacedObjectState，也不会擅自重新抓取物体。

## 文件

- scripts/models.py：Skill 内部模型和 Action 参数。
- scripts/controller.py：短计划、观测校验和局部恢复策略。
- scripts/skill.py：Stage 运行、流式反馈、Agent 决策和 on_stop。
- references/observations.md：Pilot 与 Skill 之间的低频业务观测契约。
- tests/test_skill.py：成功、恢复、Agent 决策和停止测试。
