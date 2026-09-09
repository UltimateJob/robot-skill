# Semantic Robot Skill

[English](README.md) | [简体中文](README.zh-CN.md)

🧩 Task-level robot skills and their Python worker SDK. Skills coordinate actions through the execution context; they do not replace AbilityFramework, Robot SDK, or the physics Runtime.

## Structure

- `semantic_robot_skill_sdk/` — worker protocol, execution context, and SDK.
- `semantic_robot_skills/skills/` — navigation, grasp-object, and place-object packages.
- `tests/` — worker/SDK tests; individual skills also contain tests.

## 🛠 Build and test

Requires Python **3.11+** and uv; quick-start uses **3.13**.

```bash
uv venv --python 3.13
uv pip install -e . pytest
PATH="$PWD/.venv/bin:$PATH" make test
uv build --wheel
```

The output `dist/semantic_robot_skill_sdk-*.whl` contains the worker SDK. It is **not** the distributable collection of Robot Skills.

## Package and deploy

Each Skill is a separate package with `SKILL.md`, entry code, and locked requirements. Quick-start uses Semantic Framework's `scripts/refresh_v050_mujoco.py` to package and publish the three Skills to the Server registry after Server starts.

Robot Bundles supply the execution environment; their required Skill IDs and versions must match the registry. The worker speaks a machine protocol over standard input/output and is normally launched by the managed runtime, not used as an interactive shell.

## Troubleshooting

“Robot Skill not installed” means the required registry package/version is missing. Building the SDK Wheel or activating a Robot Bundle does not fix that by itself: publish the exact requested Skill version and retry.

Start with Fake/simulation tests. A Skill may cause physical motion when connected to hardware; only run it in a controlled environment.

[Detailed technical reference](README.reference.md) · [Skill packages](semantic_robot_skills/skills/)

## License

Copyright 2026 InsightOS. First-party code: [Apache-2.0](LICENSE). See [NOTICE](NOTICE) and [license scope](LICENSE_SCOPE.md) for third-party components and assets.
