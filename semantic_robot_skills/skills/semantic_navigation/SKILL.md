---
name: semantic-navigation
description: 导航到Robot Agent选择的业务目标，由Ability实时解析工位并独立验证到达和携物状态
category: robot_skill
version: 0.4.7
runtime:
  api_version: 1
  python: ">=3.11"
  entrypoint: scripts.skill:run
  stop_entrypoint: scripts.skill:on_stop
  input_model: scripts.models:SemanticNavigationInput
  state_model: scripts.models:SemanticNavigationState
  result_model: scripts.models:SemanticNavigationResult
  controllers: {}
required_actions:
  - { type: sensor.capture_rgbd, schema_version: 2 }
  - { type: robot.get_state, schema_version: 2 }
  - { type: robot.verify_tool_load, schema_version: 2 }
  - { type: perception.locate_object, schema_version: 2 }
  - { type: navigation.plan_route, schema_version: 2 }
  - { type: navigation.follow_route, schema_version: 2 }
  - { type: navigation.verify_arrival, schema_version: 2 }
stop_actions:
  - { type: navigation.follow_route, schema_version: 2 }
debug_input:
  target:
    target_ref: pallet-b-slot-r1-c1
    pose:
      frame_id: world
      position_m: [1.19, 1.29, 0.16]
      orientation_xyzw: [0.0, 0.0, 0.7071068, 0.7071068]
  navigation_purpose: carry_to_place
  carried_object_ref: tote-large-smoke
  maximum_speed_mps: 0.05
  arrival_radius_m: 0.03
  minimum_clearance_m: 0.05
---

# 语义导航

## Stage 图片证据

关键 Stage 入口及最终完成点使用已有 `sensor.capture_rgbd` 只读能力，各采一帧 RGB；
同一 Execution/Stage/采集点使用稳定 Action key，恢复或局部重试不重复拍摄。
使用 R1 Pro 两种 Robot Profile 声明的通用 `camera.rgb`（不依赖 layout），不采 Depth。
当前 SkillContext 不暴露传感器目录，因此此型号默认值不从地图、Prompt 或宿主机路径推测。
采集失败或 Pilot 未导入图片时上报 `stage.evidence_unavailable`，不改变动作完成判断；
retreat 与停止入口不插入采集。图片的真实 source/observed_at 随 Observation 保留，
由 Pilot 原有 Artifact 链路上传；Server 是否可展示以同步状态为准。
图片仅作执行证据，不代替工具承载、到达或稳定性等独立物理验证。

## 目标

将机器人导航到已经解析的语义目标附近，并使用距离、位姿或视觉证据确认已经到达。

本 Skill 只描述 Stage、Action、反馈和恢复逻辑。设备连接、底层导航实现和通信协议由共享 Runtime 后面的能力框架负责。

## 输入与结果

输入包括：

- `target`：Robot Agent选择的业务目标引用、当前场景中的目标中心Pose提示和约束。
  `approach_grasp/carry_to_place`的Robot基座工位由Navigation Ability根据实时
  SceneSnapshot、支撑面和Robot Profile解析；Semantic Map只在规划时提供参考；
- `navigation_purpose`：`approach_grasp/carry_to_place/transit`，说明本次导航用途，
  不与 Skill 内部 Stage 混用；
- `carried_object_ref`：携物导航时用于实时复核对象身份，不携带上一 Skill 的状态；
- `arrival_radius_m`：允许的到达半径；
- `maximum_speed_mps`：导航最大速度；
- `minimum_clearance_m`：空载时的最小净空；携物时 Controller 会结合物体尺寸自动增大；

成功结果包括最终位姿引用、到目标的距离、最后一条路线引用和证据引用。携物状态仅保存在本次Execution检查点中，不进入结果，也不要求调用方复制给放置Skill。

### 可执行输入

以下示例是 `carry_to_place` 的完整形状。`target.pose`表达目标实体中心提示，不要求
Robot Agent手算底盘工位；Ability会返回本次实际使用的`resolved_target`。字段名必须与示例一致：
`position_m`、`orientation_xyzw` 和嵌套的 `target.pose` 不能改写成扁平
`position` 或 `orientation`。

```json
{
  "target": {
    "target_ref": "region://gate-nav-b",
    "pose": {
      "frame_id": "world",
      "position_m": [1.2, 0.4, 0.0],
      "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
      "revision": "gate-generation-1:1"
    },
    "constraints": {}
  },
  "navigation_purpose": "carry_to_place",
  "carried_object_ref": "tote-large-smoke",
  "maximum_speed_mps": 0.05,
  "arrival_radius_m": 0.03,
  "minimum_clearance_m": 0.05
}
```

Skill开始和到达后分别组合 `robot.get_state`、`robot.verify_tool_load` 与
`perception.locate_object` 的实时Observation；Ref只用于核对对象身份，不读取上一Skill结果。非携物导航可以省略 `carried_object_ref`。

## Stage

1. `validate_target`：复核Agent选择的业务目标和Pose提示；
2. `plan_route`：Ability从实时Scene解析Robot工作侧并由SDK生成路线；
3. `navigate`：执行路线并消费流式进度、阻塞、定位和携物反馈；
4. `verify_arrival`：独立验证是否达到语义目标。

## 观测与完成判断

- 目标位置必须携带观测版本；
- 路线阻塞或定位失效时，当前导航 Action 先停止，再重新规划；
- 路线或实时定位状态失效时，停止旧路线并请求 Agent 提供新的业务目标或策略；
- `navigation.follow_route` 成功不等于 Skill 完成，必须通过 `verify_arrival`；
- 携物时速度自动限制为不高于 0.4 m/s，路线净空根据物体尺寸收紧；
- 携物时 `verify_arrival` 必须同时确认到达和仍稳定持有同一物体；
- 物体滑移、掉落或负载异常时，执行侧先停底盘，再请求 Robot Agent；
- 验证结果为 `uncertain` 时，请求 Robot Agent；Robot Agent 可以委派 Monitor Agent 分析证据。

## 局部恢复

脚本可以在内部有限恢复预算内：

- 复核 Agent 给出的新目标；
- 停止已失效的路线并重新规划；
- 路线执行失败后重新规划；
- 再次验证到达状态。

脚本不会在停止结果未知时启动下一项 Action。

## 需要 Robot Agent 决策的情况

- 目标已失效，需要 Agent 重新解析；
- 路线规划或执行的本地恢复预算耗尽；
- 到达验证不确定；
- 当前 Action 因严重异常停止；
- 需要终止当前 SubTask。

Robot Agent 只能返回本 Skill 定义的类型化决定，不能注入 Python 代码或任意 Stage 状态。
Robot Agent 不能直接替代 `verify_arrival` 宣告到达；语义判断可以辅助验证，但最终
结果仍必须由类型化到达与持物观测形成。

## 安全停止

严重异常必须由 Action 执行侧先停止，再把停止结果和证据反馈给脚本。`on_stop` 使用 Runtime 提供的专用停止入口，不依赖普通 Action 继续运行。
