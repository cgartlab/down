# Changelog

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

项目采用 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

- v0.1.0 初版骨架

## [0.1.0] - 2026-10-10

### Added

- **SKILL.md**：主入口，含三条元规则（不静默安装 / 最小步骤 / 验证才算完成）、5 Phase 工作流、Pitfalls 清单（来自实战：X `--no-playlist`、`hls-*` vs `http-*`、Nitroflare 硬墙、Windows `python -c` 反引号陷阱等）。
- **scripts/detect.py**：URL 探测器。stdlib only，零网络请求。分类：`platform_video` / `direct_file` / `torrent` / `magnet` / `unknown`。
- **references/tool-matrix.md**：curl / yt-dlp / aria2c 能力边界与选择规则。
- **references/detectors.md**：detect.py 字段契约与判定优先级。
- **references/commands.md**：各 kind 的命令配方（含验证命令）。
- **references/anti-bot.md**：Nitroflare / Alfafile / CGPersia 类站点的识别与降级。
- **AGENTS.md**：本仓库编码约定（3 条元规则 + 提交规约 + 自检命令）。
- **README.md**：快速上手与目录结构。
- **evals/test_detect.py**：detect.py 单元测试（stdlib unittest，11 个用例覆盖所有 kind 与边界）。

### Design notes

- **skill 不硬编码任何默认路径**：路径解析走三级优先级——用户显式指定 → 环境偏好（Hermes memory / `~/.downrc` / `DOWN_DEFAULT_DIR`）→ 临时目录兜底。skill 逻辑与用户本机偏好解耦：本机偏好是环境层配置，不是 skill 逻辑。
- **强制询问工具安装**：不静默 `uv tool install` 或 `winget install`。
- **探测器不发网络**：URL 探测阶段无副作用，避免误触反爬与泄露 Referer。
- **工具矩阵优先级**：curl → yt-dlp → aria2c，能用更轻量的解决就不用更重的。

### Known limitations

- 反爬站点（Nitroflare / Alfafile 等）无法通过 CLI 绕过——这是**特性**不是 bug，skill 会如实报告。
- 仅支持 POSIX shell 命令配方（`references/commands.md`）；PowerShell 版本留待 v0.2。
- 无 headless 浏览器驱动——不尝试破解 JS 挑战（RandHash2 / Cloudflare turnstile 等）。
