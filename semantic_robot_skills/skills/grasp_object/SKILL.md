---
name: grasp-object
description: 抓取指定物体并形成经过独立验证的 HeldObjectState
category: robot_skill
version: 0.4.23
runtime:
  api_version: 1
  python: ">=3.11"
  entrypoint: scripts.skill:run
  stop_entrypoint: scripts.skill:on_stop
  input_model: scripts.models:GraspObjectInput
  state_model: scripts.models:GraspObjectState
  result_model: scripts.models:GraspObjectResult
  controllers:
    depalletizing.grasp: scripts.controller:DepalletizingGraspController
required_actions:
  - { type: sensor.capture_rgbd, schema_version: 2 }
  - { type: perception.locate_object, schema_version: 2 }
  - { type: grasp.generate_candidates, schema_version: 2 }
  - { type: grasp.plan_transport_posture, schema_version: 2 }
  - { type: gripper.set_opening, schema_version: 2 }
  - { type: motion.move_end_effector, schema_version: 2 }
  - { type: perception.verify_pregrasp, schema_version: 2 }
  - { type: gripper.close, schema_version: 2 }
  # 夹紧已经产生物理影响后，普通执行路径也可能需要先 hold 再请求 Agent
  # 决策；它不仅是外部 stop 回调使用的动作，因此必须同时声明为可执行 Action。
  - { type: gripper.hold_object, schema_version: 2 }
  - { type: motion.lift_held_object, schema_version: 2 }
  - { type: perception.verify_grasp, schema_version: 2 }
  - { type: robot.get_state, schema_version: 2 }
  - { type: robot.verify_tool_load, schema_version: 2 }
stop_actions:
  - { type: gripper.hold_object, schema_version: 2 }
debug_input:
  target:
    object_ref: tote-large-smoke
    pose_hint: null
    extent_hint_m: [0.6, 0.4, 0.34]
    category_hint: tote
  tool_refs: [component://tool/left, component://tool/right]
  preferred_strategy: auto
  minimum_lift_height_m: 0.08
---

# 去码垛抓取

## Stage 图片证据

关键 Stage 入口及最终完成点使用已有 `sensor.capture_rgbd` 只读能力，各采一帧 RGB；
同一 Execution/Stage/采集点使用稳定 Action key，恢复或局部重试不重复拍摄。
使用 R1 Pro 两种 Robot Profile 声明的通用 `camera.rgb`（不依赖 layout），不采 Depth。
当前 SkillContext 不暴露传感器目录，因此此型号默认值不从地图、Prompt 或宿主机路径推测。
采集失败或 Pilot 未导入图片时上报 `stage.evidence_unavailable`，不改变动作完成判断；
retreat 与停止入口不插入采集。图片的真实 source/observed_at 随 Observation 保留，
由 Pilot 原有 Artifact 链路上传；Server 是否可展示以同步状态为准。
图片仅作执行证据，不代替工具承载、到达或稳定性等独立物理验证。

## 执行入口

- 使用 `scripts/skill.py:run` 推进可恢复 Stage。
- 使用 `scripts/skill.py:on_stop` 收敛停止后的物理状态。
- 让 Runtime 注册 `depalletizing.grasp` Controller；不要由脚本连接具体设备。
- 读取详细观测契约时参见 [references/observations.md](references/observations.md)。

## 可执行输入

Robot Agent 调用 `robot.run` 时必须使用下面的字段名；物体引用和双工具引用来自
Task 输入，不需要先改写成坐标或 Ability 参数：

```json
{
  "target": {
    "object_ref": "tote-large-smoke",
    "pose_hint": null,
    "extent_hint_m": [0.6, 0.4, 0.34],
    "category_hint": "tote"
  },
  "tool_refs": ["component://tool/left", "component://tool/right"],
  "preferred_strategy": "auto",
  "minimum_lift_height_m": 0.08
}
```

Robot Agent 可以提供 `target.pose_hint` 作为参考，但 Skill 不把 Semantic Map 的 generation、revision
或来源 ID 当成执行事实。不得传入固定轨迹点或 Robot SDK 参数；目标位姿和候选必须
由 Skill 开始后的实时观测与抓取规划 Action 产生。

## 大期望

只有同时满足以下条件，才把本 Skill 判定为完成：

1. 确认抓取的是 `object_ref` 指向的物体；
2. 物体由双侧工具稳定承载并抬升到最小高度；
3. 持物状态持续达到要求的稳定时长；
4. 独立验证能力返回足够置信度；
5. 双末端整理到根据箱体尺寸和当前抓取关系计算出的携物姿态；
6. 输出本 Skill 定义的 `HeldObjectState`，仅供审计，后续 Skill 会重新读取实时状态。

原子 Action 返回 `succeeded` 不等于 Skill 完成。

## Stage 与期望

1. `observe_target`
   - 获取带 `revision` 的新鲜 `target_pose`；
   - 根据实际目标位姿生成一组 `grasp_candidates`；
   - 禁止使用固定物体中心点或硬编码抓取坐标。
2. `approach`
   - Controller 为当前候选生成“打开夹具 → 箱体外侧高位转移 → 外侧下降 → 水平插入 → 独立核对”的短计划；
   - 高位转移和外侧下降避免夹具在尚未到达侧面凹槽前扫过箱沿；这些位姿必须来自
     当前抓取候选，Skill 不自行猜测箱体或夹具几何；
   - 目标版本变化、位姿误差超限或候选不可达时废弃旧短计划。
3. `grasp`
   - 逐侧执行夹具闭合并消费接触、夹持力和滑移反馈；
   - 在安全边界内切换候选或刷新观测，不进行无界重试。
4. `lift_and_verify`
   - 抬升时持续观察滑移和物体随动；
   - 抬升完成后调用独立验证能力；
   - 验证达到抓取期望后进入携物姿态准备。
5. `prepare_transport`
   - 抬升验证后，GraspPlanning 根据实时箱体位姿和本次真实工具—箱体关系提供双末端携物姿态；
   - 收拢时持续检查接触、力和滑移；
   - 完成后组合实时Robot状态、工具承载验证和物体观测，成功后才结束Skill。

## Controller 与原子能力

让 Controller 只规划当前 Stage 所需的少量 Action。把轨迹点、控制周期、力控环和
设备协议留在 Pilot 后面的原子能力实现中。传统规划器、状态机、行为树和 VLA 都可
作为这些原子能力的实现，只要遵守同一输入、反馈、取消和结果契约。

## 局部恢复与 Agent 决策

在脚本声明的次数和安全范围内执行以下局部恢复：

- 刷新目标观测和候选；
- 切换到评分后的下一个候选；
- 重新生成 Approach 短计划；
- 在仍确认持物时再次独立验证。

出现以下情况时请求 Robot Agent 的类型化决定：

- 局部恢复次数耗尽；
- 停止后物理状态为 `possible` 或 `unknown`；
- 抬升时滑移或物体不再随双工具移动；
- 需要改变抓取策略、显式选择候选或终止当前 SubTask。

拒绝计划版本不匹配的 Agent 决定。Robot Agent 不得向 Skill 注入任意 Python、轨迹点
或内部 Stage 状态。

## 停止

收到停止请求后，不再产生普通 Action。若已经持物，使用专用停止入口同时保持两个工具，执行
`gripper.hold_object` 并明确返回是否安全、当前物理状态和是否需要人工介入。未确认
安全保持时不得把 Skill 标记为安全停止。
