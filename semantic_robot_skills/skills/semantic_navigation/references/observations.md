# 语义导航观测约定

本文只描述示例脚本会读取的低频业务观测。高频碰撞、限位和急停检测仍由 Action 执行侧负责。

| kind | 关键字段 | 用途 |
|---|---|---|
| `navigation_progress` | `distance_to_target_m`、`progress_m` | 展示导航进度 |
| `route_blocked` | `blocked` | 判断当前路线是否需要停止并重规划 |
| `localization_state` | `valid` | 判断本地定位是否仍然有效 |
| `target_revision` | `revision` | 判断目标位置观测是否发生变化 |
| `robot.state` | `tool_states`、`end_effectors`、`generation` | 从当前 Robot Profile 发现实际工具并取得末端实时状态 |
| `robot.tool_load` | `condition_satisfied`、`tools[]`、`slip_detected`、`overload_detected`、`sensor_fault` | 导航开始和到达时复核期望工具集合的实时承载条件 |
| `target_pose` | `object_ref`、`pose`、`extent_m`、`identity_confidence` | 重新观测携带物体的身份、位姿和包络，用于本次路线与负载判断 |
| `robot_pose` | `pose_ref` | 保存最终机器人位姿引用 |
| `arrival_evidence` | `distance_to_target_m`、`target_visible` | 验证是否达到语义目标 |

## 严重异常

当反馈的 `severity` 为 `critical` 时，执行侧必须已经启动停止流程。Python 脚本只读取唯一终态并汇总证据；不能等待 Robot Agent 或 Monitor Agent 分析后才停止。

携物状态异常也按严重异常处理。到达验证必须与新鲜的 Robot 状态、工具承载验证和
物体观测组合判断；如果只返回“底盘已到达”而没有负载证据，Skill 不得宣告完成。
组合状态只写入本次 Execution 检查点，不进入结果，也不会要求下一项 Skill 复制整段
JSON。

## 数据体积

小型数值和状态可以直接放在 `Observation.value` 中。图片、视频、点云和长时间序列通过 `data_ref` 或 `evidence_refs` 引用，不进入脚本状态和 Agent 请求正文。

## 目标变化

Ability发现本次目标位姿或路线已经失效时，脚本必须：

1. 停止当前导航 Action；
2. 清除旧目标位姿和路线；
3. 在现有业务目标范围内重新取得可执行位姿，无法确定时请求 Robot Agent；
4. 使用新观测重新规划。

这里比较的是本次 Ability 的实时目标观测，不是 Semantic Map generation。地图只在
Agent规划时提供参考，不能成为 Robot Skill 拒绝当前物理执行的条件。
