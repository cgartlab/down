---
name: down
description: 'Analyze a URL and download it with minimal steps.'
version: 0.1.0
author: cgart, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [download, yt-dlp, aria2, curl, magnet, torrent]
    related_skills: [file-download, blocked-page-recovery]
---

# Down — 万能下载 skill

分析任何 URL，用最少的步骤把它落到本地。**只使用当前环境已装工具**，任何安装动作必须先询问用户批准。

## 何时使用

- 用户扔一个 URL 过来，语义是"下载/保存/我要这个文件"。
- 用户明确说 "下载"、"存下来"、"拉过来"、"down this"、"get this" 等。

## 何时不用

- 用户只是要看网页内容 → `web_extract`。
- 用户只是要看视频但不用保存 → 直接给链接。
- 用户要求生成文件（不是下载外部）→ 走对应工具。

## 触发方式

用户消息里出现 URL（且语义是下载/保存），即自动激活本 skill。**不需要用户显式说"用 down"**。

## URL 到手后的第一件事：确定保存路径

- 用户**明确说了路径**（如 "下载到 D:\Movies"）→ 直接用那个路径。
- 用户**没明确说** → 默认保存到**临时目录**（`$TMPDIR` 或 `~/.cache/down/<session-id>/`）。**不询问**——用户已经说过"没说明就存临时目录"是标准行为。

**例外**：如果用户在同一会话里对**另一个下载**说过保存路径，可提示"这次也存那里吗？"作为软性建议，但不用 `clarify` 阻塞。

## 三条不可让渡的规则

1. **不静默安装**：任何工具（yt-dlp / aria2 / 其他）缺失时，先向用户展示"要装什么、用哪个包管理器、大约多大"，等一句"go"再动手。绝不默认 `uv tool install` 或 `winget install`。
2. **只用最小步骤**：能用 `curl` 解决的不上 yt-dlp；能用 yt-dlp 解决的不上 aria2。工具选择规则见 `references/tool-matrix.md`。
3. **验证才算完成**：下载成功后必须 `ffprobe`（媒体）或 `sha256sum`（其他）核验，把真实数字写进回复；不能仅凭退出码声称成功。

## 工作流

```
[URL 到手]
   |
Phase 1 — 探测（scripts/detect.py --url "<url>"）
   |  JSON 出：kind / dest_name / suggested_tool / verify_cmd
   |
Phase 2 — 工具检查（suggested_tool 是否在 PATH？）
   |  ├─ 在 → 直接执行
   |  └─ 缺失 → 询问用户是否安装（不装则降级到 curl，能过就过）
   |
Phase 3 — 执行下载（curl / yt-dlp / aria2c 之一）
   |  输出到 Phase 0 确定的路径
   |
Phase 4 — 验证
   |  跑 verify_cmd（ffprobe / file / sha256sum）
   |  失败 → 报告失败原因（不重下、不编造）
   |
Phase 5 — 回复用户
        MEDIA:<绝对路径> + 规格摘要 + 保存路径
```

## Phase 1 — 探测

跑 `python scripts/detect.py --url "<url>"`（Windows）或 `python3 scripts/detect.py --url "<url>"`（POSIX）。返回 JSON：

```json
{
  "url": "https://...",
  "kind": "platform_video | direct_file | torrent | magnet | unknown",
  "host": "youtube.com",
  "suggested_tool": "yt-dlp",
  "dest_name": "some-title.mp4",
  "verify_cmd": "ffprobe -v error -show_entries ...",
  "install_hint": { "name": "yt-dlp", "install": "uv tool install yt-dlp", "fallback": "curl -L" }
}
```

判定规则（host 白名单 + URL 特征匹配）见 `references/detectors.md`。

## Phase 2 — 工具检查

- `yt-dlp --version` 失败 → 提示"要装 yt-dlp 吗？`uv tool install yt-dlp`（Python 包，~3 MB）"。
- `aria2c --version` 失败 → 提示"要装 aria2 吗？`winget install aria2.aria2`（~4 MB）"。
- `curl --version` 失败 → 报错，本 skill 无法工作（curl 是最后兜底）。
- 用户拒绝安装 → 降级：能 curl 直链的用 curl；torrent/magnet 只能报告"无法处理，需 aria2"。

## Phase 3 — 执行下载

按 kind 走不同配方，完整命令见 `references/commands.md`。摘要：

| kind | 命令骨架 |
|------|---------|
| platform_video | `yt-dlp --no-playlist -f "mp4/best" -o "<dest>/<name>.%(ext)s" "<url>"` |
| direct_file | `curl -L --fail -o "<dest>/<name>" "<url>"` |
| torrent / magnet | `aria2c -x 8 -s 8 -k 1M -M 1M -o "<name>" -d "<dest>" "<url>"` |
| unknown | 先 `curl -I` 看 Content-Type，能识别就当 direct_file，否则问用户 |

## Phase 4 — 验证

- 媒体（.mp4/.mkv/.mp3/.m4a）：`ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_type,codec_name,width,height -of default=nw=1 "<file>"`。
- 归档（.rar/.zip/.7z）：`7z t "<file>"` 或 `unrar t "<file>"`（若装了）。
- 其他：`file "<file>"` + `sha256sum "<file>"`。

**验证失败 ≠ 下载失败**。如实报告（如"文件已下载 5 MB 但 ffprobe 报 invalid data"），别自己再下一遍。

## Phase 5 — 回复

回复结构（三行）：
1. `MEDIA:<绝对原生路径>`（单独一行，Windows 用 `D:\...`，POSIX 用绝对路径）。
2. 规格：codec、WxH、duration、size（用真实数字）。
3. 保存路径确认 + 一句工具选择说明（"用 curl 直下，无需 yt-dlp"）。

## Pitfalls（已知坑，来自实战）

- **`yt-dlp` 遇到 x.com 必须带 `--no-playlist`**：不带会把整条 post 的多视频都拉下来。
- **X 上选 `http-*` 格式，不要 `hls-*`**：hls 通常 video-only，需要再合并 audio，多一步。
- **不要预设登录**：Twitter/YouTube 的 yt-dlp extractor 自带 guest token，未登录就能跑；只有 extractor 报 auth 错误才去折腾 cookies。
- **输出模板保留扩展名**：`-o "...%(ext)s"` 让下载器选真实容器；写死 `.mp4` 会在遇到 webm/mkv 时炸。
- **Windows 上 `python -c "..."` 会吃掉反引号**（当命令替换执行）：所有复杂命令写到 .py 文件后 `python xxx.py` 执行，不要用 `-c` 或 heredoc。
- **Windows 上 `curl` 输出到 `/tmp`** 实际落到 `C:\Users\<user>\AppData\Local\Temp\`（MSYS 转换）：验证/后续访问要用真实路径。
- **Nitroflare 硬墙**：`RandHash2` JS 挑战 CLI 无法绕过 → 如实报告过不去，不要耗时间硬试。
- **Alfafile 免费流**：需要 JS 渲染 30 秒倒计时 + captcha，curl 拿不到直链 → 同上。
- **`uv tool install` 装的二进制在 `~/.local/bin`**：每次 `terminal` 调用是新 shell，必须显式 `export PATH="$HOME/.local/bin:$PATH"` 才能找到。

## 与旧 skill `file-download` 的关系

`file-download` 是老版本，硬编码 `D:\Download`、假设 yt-dlp 存在。**本 skill 是它的正式替代**：
- 保存路径默认临时目录（不再默认 D:\Download；用户显式指定则优先）。
- 工具安装强制询问（不再默认 `uv tool install`）。
- 覆盖 torrent/magnet（file-download 不覆盖）。
- 保留 file-download 的所有 X/Twitter 最佳实践。

用户显式加载本 skill 后，新下载请求应走 down，不走 file-download。

## Verification

- 文件物理存在于目标路径，size > 0，文件名描述性。
- ffprobe/file/sha256sum 输出与文件大小一致。
- `MEDIA:` 路径指向同一个文件。
- 工具安装动作前有过一次用户批准（除非用户显式说"你决定"）。
