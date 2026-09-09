# 放置 Skill 观测契约（schema v2）

Pilot 可以在内部消费高频关节、力、触觉、图像和控制反馈，但只向 Robot Skill
提交完成当前 Stage 所需的低频类型化 Observation。所有观测都必须带 source、
observed_at、revision 或 evidence_refs，恢复后仍可追踪。

## 放置前实时持物复核

放置 Skill 不读取前一项 Skill 的 `HeldObjectState`，也不依赖全局持物状态。Stage入口
组合以下三类新鲜观测，在本次 Execution 检查点中建立局部持物事实：

- `robot.state`：从 `tool_states` 发现当前 Profile 的双工具，并通过 `side` 关联
  `end_effectors` 中的实时工具位姿；
- `robot.tool_load`：对发现的期望工具集合验证接触、力、相对滑动、过载和传感器状态；
- `target_pose`：由 ObjectPerception 按输入 `object_ref` 重新观测物体身份、位姿与尺寸。

要求 `robot.tool_load.condition_satisfied=true`，无滑移、过载和传感故障，且实时物体
身份与输入一致。该组合结果只供本次放置流程规划和检查，调用方不传Robot或工具状态。

## placement.target_slot

value：

    {
      "schema_version": 2,
      "target_ref": "pallet-b-slot-r1-c1",
      "placement_pose": { "Pose3D": "完整内容" },
      "approach_vector": [0.0, 0.0, 1.0],
      "free": true,
      "reachable": true,
      "occupants": [],
      "support_surface_ref": "pallet-b",
      "revision": "scene-42",
      "confidence": 0.97,
      "evidence_refs": ["artifact://slot-observation"]
    }

目标 Region 表达一个垂直堆叠列。`placement_pose` 由实时占用物体的几何中心、AABB、
支撑平面和待放物体尺寸计算；它不是固定高度的单格落点。approach_vector 由感知、
码垛规划器或设备侧 Controller 产生。Skill不提供固定世界坐标。观测过期、满层、
箱型不兼容或不可达时，Skill 可以在内部预算内刷新。

## manipulation.object_released

释放 Action 的流式反馈：

    {
      "object_ref": "object://box-17",
      "tools": {"component://tool/left": {"hook_contact": false, "clamp_contact": false}},
      "gripper_empty": false,
      "stable_load": true
    }

每次 Action 只释放一个工具。第一侧释放后必须确认另一侧稳定承载；第二侧释放后必须确认两个工具为空。它只证明当前工具释放，不证明物体已经稳定或位于目标容差内。反馈应结合夹爪位置、
接触或负载变化，并把证据引用写入 Observation。

## placement.object_stability

必须在撤离后由独立感知源产生。value：

    {
      "state": { "共享 PlacedObjectState": "完整内容" },
      "within_target": true,
      "stable": true,
      "observed_displacement_m": 0.002,
      "observed_duration_ms": 1000,
      "support_contact": true,
      "gripper_empty": true,
      "independent_verification": true
    }

完成判定还会检查：

- PlacedObjectState.stable 为 true。
- position_error_m 和 orientation_error_rad 在 PlacementTarget 容差内。
- 已覆盖 PlacementTarget.stability_duration_ms 指定的稳定窗口。
- PlacedObjectState.observed_duration_ms 明确记录已经覆盖的稳定窗口。
- PlacedObjectState.gripper_empty 为 true。
- 完成判定只读取正式 Observation 的嵌套 state 和布尔字段，不读取 Action output 或来源名称猜测。
- 稳定放置后还必须完成 Profile 的 `travel` 命名姿态；姿态恢复失败只报告 Robot
  未恢复行走姿态，不得重新抓取已经放稳的物体。

## 安全和不确定状态

- 任意流式反馈 severity=critical 时，Skill 停止当前 Action 并上报未知物理状态。
- release 最终结果缺少明确释放观测时，本次 Skill 以
  `RELEASE_TOOL_STATE_UNKNOWN` 结束，不得自动重放 release，也不得原地继续接近或撤离；
  Robot Agent 只能在新的复核/恢复 SubTask 中处理。
- 释放后稳定性验证失败时，不得伪造 PlacedObjectState；局部复核耗尽后请求 Agent。
- on_stop 的 StopOutcome 是停止事实，不是放置成功事实。
