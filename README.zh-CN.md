# Semantic Robot Skill

[English](README.md) | [简体中文](README.zh-CN.md)

🧩 任务级 Robot Skill 与 Python Worker SDK。Skill 通过执行上下文组织动作，不替代 AbilityFramework、Robot SDK 或物理仿真 Runtime。

## 工程结构

- `semantic_robot_skill_sdk/`：Worker 协议、执行上下文与 SDK。
- `semantic_robot_skills/skills/`：导航、抓取、放置三个 Skill 包。
- `tests/`：Worker / SDK 测试；各 Skill 另有自己的测试。

## 🛠 构建与测试

需要 Python **3.11+** 和 uv；quick-start 使用 **3.13**。

```bash
uv venv --python 3.13
uv pip install -e . pytest
PATH="$PWD/.venv/bin:$PATH" make test
uv build --wheel
```

产物 `dist/semantic_robot_skill_sdk-*.whl` 只包含 Worker SDK，**不是** Robot Skill 分发集合。

## 打包与部署

每个 Skill 都是独立包，包含 `SKILL.md`、入口代码与锁定依赖。quick-start 通过 Semantic Framework 的 `scripts/refresh_v050_mujoco.py` 打包三个 Skill，并在 Server 启动后发布到注册表。

Robot Bundle 提供执行环境，其要求的 Skill ID 与版本必须与注册表一致。Worker 通过标准输入输出使用机器协议，通常由托管运行时启动，不是交互式命令行。

## 常见问题

“Robot Skill 尚未安装”表示注册表缺少指定包或版本。仅构建 SDK Wheel 或激活 Robot Bundle 无法解决，需要发布请求的精确 Skill 版本后重试。

从 Fake / 仿真测试开始；连接硬件后 Skill 可能产生实际运动，只能在受控环境执行。

[详细技术参考](README.reference.md) · [Skill 工程](semantic_robot_skills/skills/)

## 许可证

Copyright 2026 InsightOS。自有代码采用 [Apache-2.0](LICENSE)；第三方组件与资产请查看 [NOTICE](NOTICE) 和[许可范围](LICENSE_SCOPE.md)。

## 三个平台的构建复现

参见 [glibc、musl 与 macOS 构建说明](README.build.md)：包含已锁定的源码版本、实际脚本入口、工具要求、本地与 CI 指令、产物位置和平台验证范围。
