# 去码垛抓取观测契约（schema v2）

本文描述抓取 Stage 脚本读取的低频业务观测。碰撞、限位、过流和急停等高频保护由
Pilot 本地安全链路与原子能力执行器负责，不能等待本脚本或大模型处理。

## 目标与候选

| `kind` | `subject_ref` | `value` 关键字段 | 生产者与用途 |
|---|---|---|---|
| `target_pose` | 待抓物体引用 | `object_ref`、`pose`、`extent_m`、`identity_confidence` | 感知或定位能力；建立带版本的真实目标位姿 |
| `grasp_candidates` | 待抓物体引用 | `target_revision`、`candidates[]` | 抓取规划器或 VLA；给出候选的高位转移、外侧接近、插入、携物姿态、策略和评分 |

`target_pose.revision` 或其内部 `pose.revision` 必须存在。候选的
`target_revision` 必须与当前目标版本一致，否则整个候选集合失效。目标位姿和候选必须
来自当前观测，禁止用模板内固定中心点代替。

## Approach

| `kind` | `value` 关键字段 | 用途 |
|---|---|---|
| `end_effector_progress` | 实现自定义的进度、距离或剩余时间 | 前端和 Agent 的低频进度展示 |
| `collision_proximity` | 距离或风险等级 | 供原子能力本地调整或触发停止 |
| `target_revision` | `revision` | 检测目标在接近过程中是否变化 |
| `pregrasp_state` | `candidate_id`、`target_revision`、`reached`、`position_errors_m` | 独立判断是否达到当前 Stage 期望 |

## 夹持与抬升

| `kind` | `value` 关键字段 | 用途 |
|---|---|---|
| `grasp_contact` | `candidate_id`、`object_ref`、`tools`、`contact_confirmed`、`stable_bilateral_load`、`slipping`、`overloaded` | 按 tool_ref 判断双侧接触；最终稳定承载由抬升监控与 VerifyGrasp 独立确认 |
| `tool_state` | 每个工具的开度、接触、负载、滑移、过载和故障 | 执行器诊断与 Trace 展示 |
| `lift_progress` | `candidate_id`、`lift_height_m`、`object_follows_tools`、`stable_load`、`slip_detected`、`overloaded` | 判断双侧承载和抬升安全包络 |

流式观测必须带单调递增的 `ActionFeedback.sequence`。反馈 `severity=critical` 时，
执行侧必须先进入停止过程；脚本只消费唯一终态并决定是否能继续。

## 独立完成验证

`grasp_verification.value` 必须包含：

- `candidate_id`；
- `held`；
- `stable_bilateral_load`；
- `lift_height_m`；
- `stable_duration_ms`；
- `slipping`、`overloaded`；
- `object_pose`；
- `tool_poses`，且键集合必须与输入 `tool_refs` 一致。

验证能力必须返回物体和双工具的真实位姿，并与 `gripper.close` 和 `motion.lift_held_object` 的执行结果相互独立。它可以
融合夹爪负载、视觉、深度或其他传感器，但不能仅把原子 Action 的成功状态原样返回。

## 携物姿态

`prepare_transport` 使用抓取验证后产生的 `transport_posture` Observation。末端目标由当前 Robot
底盘位姿、实时物体几何和双工具抓取关系计算，不能是某种箱型的固定关节角。移动
完成后必须组合三类新鲜观测：`robot.state` 提供工具与末端实时状态，
`robot.tool_load` 验证期望双工具的承载条件，`target_pose` 重新确认物体位姿与身份。
只有三者一致表明双侧仍承载同一物体，且无滑移、过载或传感异常时，抓取
Execution 才能完成。组合得到的 `HeldObjectState` 只属于本次 Skill 的检查点和结果，
后续 Skill 会重新观测实时状态，不复制该对象。

## 大数据与证据

数值和小型结构放入 `Observation.value`。图片、视频、点云和长时间序列只通过
`data_ref` 或 `evidence_refs` 引用。Skill 状态、Agent 决策上下文和最终结果只保存稳定
引用，不复制大块原始数据。
