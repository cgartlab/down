# AGENTS.md — down 仓库编码约定

给在本仓库工作的 coding agent 的指引。

## 这是什么

`down` —— Hermes Agent Skill，一个"万能下载"技能。用户扔 URL，skill 分析后用最少的工具步骤下载到本地。

主入口：`SKILL.md`。工作流见 SKILL.md，工具矩阵见 `references/tool-matrix.md`。

## 三条元规则

1. **不静默安装工具**：脚本或 SKILL.md 里的任何安装命令必须走用户批准流程。脚本只能**检测**工具是否存在，绝不**执行**安装动作。
2. **探测器纯函数**：`scripts/detect.py` 只根据 URL 形状分类，**不发网络请求**，**不修改文件系统**。任何需要网络的判定都留给 caller（SKILL.md 的 Phase 3+）。
3. **报告如实**：任何工具缺失、硬墙站点、验证失败都必须写进回复；禁止编造下载成功或跳过验证。

## 工作约定

- **脚本黑盒**：`scripts/detect.py` 是 CLI 接口，caller 通过 `--url` 传入、读 stdout JSON。**改脚本要同步更新 `references/detectors.md` 的字段契约**。
- **只读探测**：detect.py 不写入任何文件（除了 `--help` 输出到 stdout）。任何需要落盘的逻辑都不该进 detect.py。
- **安全分层**：
  - 只读探测（detect.py）：自动执行，无副作用
  - 工具安装：必须先展示命令、大小、理由，等用户"go"
  - 文件下载：默认执行（用户明确要求了），但保存路径默认临时目录；用户明确指定则优先
- **不编造**：URL 无法识别就说 unknown；工具缺失就说缺失；下载失败就说失败。**"没查成"必须写成"没查成"，不得写成"没有"**。

## 改本仓库时

- **提交规约**：conventional commits（`feat` / `fix` / `docs` / `chore` / `test` / `refactor`）；body 讲 WHY。
- **版本策略**：技能尚在早期，`version: 0.1.0` 保持不动；变更记入 `CHANGELOG.md` 的 `[Unreleased]`。语义版本（major/minor/patch）等 v1.0 前再看。
- **改探测器要同步**：改 `detect.py` 的判定逻辑 → 同步 `references/detectors.md` 的判定表 → 同步 `evals/test_detect.py` 的测试用例。三处不一致即为漂移。
- **不要在 SKILL.md 复述 references 的细节**：SKILL.md 只做**路由**（读哪个文件）+ **流程**（Phase 顺序）+ 元规则。所有命令配方、判定表、站点清单都在 references 里。
- **加规则要配对减规则**：往 SKILL.md 或 AGENTS.md 加条文时必须同时指出可删除或合并的旧条文。文档膨胀是唯一刹车——每次修 bug 都留一条永久规则最终会淹没工作流。

## 自检（提交前跑）

```bash
# detect.py 单元测试
python -m unittest evals.test_detect -v

# 手工冒烟：跑几个不同 kind 的 URL
python scripts/detect.py --url "https://youtube.com/watch?v=dQw4w9WgXcQ"
python scripts/detect.py --url "https://example.com/file.mp4"
python scripts/detect.py --url "magnet:?xt=urn:btih:abc&dn=test"
```

## 依赖

- **必需**：Python 3.9+（detect.py 只依赖 stdlib）
- **可选**：`pytest`（如果不用 `unittest`）——v0.1 未使用，保持 unittest

## 未来方向（v0.2+）

- **反爬识别自动化**：加一个 `scripts/probe_host.py` 做 `curl -I` 探测 Content-Type 与反爬特征，返回给 caller 决定降级路径。
- **下载会话恢复**：aria2c 的 `--save-session` 已支持，缺一个"检查未完成下载"的脚本。
- **多平台命令模板**：目前命令配方假设 POSIX shell（bash/zsh）。PowerShell 版本可后加到 `references/commands-windows.md`。
- **测试矩阵扩到覆盖所有 kind 边界**：目前 evals 只覆盖 happy path。
