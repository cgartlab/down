# 工具矩阵与选择规则

本 skill 遵循**最小步骤原则**：能用 curl 解决的不上 yt-dlp；能用 yt-dlp 解决的不上 aria2。选择优先级从下往上：**优先级数字小的先试**。

## 判定决策树

```
URL 拿到手
   |
   +-- 是 magnet:?xt=... ?
   |       --> aria2c（唯一选择）
   |
   +-- URL 路径以 .torrent 结尾 ?
   |       --> aria2c（唯一选择）
   |
   +-- host 是平台站（x.com / youtube.com / bilibili.tv / ...） ?
   |       --> yt-dlp（唯一选择，直接 curl 拿不到视频流）
   |
   +-- URL 路径以文件扩展名结尾（.mp4/.pdf/.zip/...） ?
   |       --> curl -L（唯一选择）
   |
   +-- 都不匹配（unknown）
           --> curl -L -I 先探 Content-Type，能识别就当 direct_file，
               否则问用户"这是什么类型的资源"
```

## 各工具能力边界

| 工具 | 处理对象 | 依赖 | 安装命令（示例） |
|------|---------|------|-----------------|
| `curl` | 任意 HTTP(S) 直链；不支持 magnet/BitTorrent；不支持平台视频解析 | 系统自带 | 无需 |
| `yt-dlp` | 1744 个平台的视频/音频页面（YouTube, X, Bilibili, TikTok, Reddit, Vimeo, Dailymotion, Twitch 等） | Python 3.8+ | `uv tool install yt-dlp`（Windows/Linux/macOS 通用） |
| `aria2c` | BitTorrent 协议（`.torrent` 文件、`magnet:` URI）、HTTP 分块多线程 | C 二进制 | Windows: `winget install -e --id aria2.aria2`；Linux: `apt install aria2`；macOS: `brew install aria2` |

**其他候选（v0.1 未纳入，未来扩展）**：
- `uget` — 老派 curl 替代，Windows GUI 有历史，CLI 场景用不上。
- `axel` — 多线程直链下载，功能与 `aria2c -x` 重叠，无必要引入。
- `pywebhockey` 类脚本 — 特定站点破解，不进工具矩阵，遇到具体站点时按需处理。

## 工具缺失时的降级策略

| 场景 | 首选 | 若首选缺失，用户拒绝安装 |
|------|------|--------------------------|
| 平台视频 | yt-dlp | **无降级**（curl 抓不到平台视频流）；如实报告"需 yt-dlp" |
| 直链文件 | curl | **无降级**（curl 是最后兜底）；无 curl 则报错终止 |
| torrent/magnet | aria2c | **无降级**（curl/yt-dlp 都不支持）；如实报告"需 aria2" |
| 平台视频，用户装 aria2c 但没装 yt-dlp | aria2c | 不适用：aria2c 不识别平台 URL |

**关键点**：torrent/magnet 与平台视频**没有互相降级的可能**——它们需要不同的工具。skill 必须诚实报告"这个 URL 类型没有已装工具能处理"，而不是花哨地猜。

## 常见 URL 类型 → 工具对照

| URL 形态 | kind | tool |
|---------|------|------|
| `https://x.com/*/status/*/video/*` | platform_video | yt-dlp |
| `https://youtube.com/watch?v=*` | platform_video | yt-dlp |
| `https://youtu.be/*` | platform_video | yt-dlp |
| `https://b23.tv/*` | platform_video | yt-dlp |
| `https://*.mp4` / `*.mkv` / `*.webm` | direct_file | curl |
| `https://*.pdf` / `*.zip` / `*.tar.gz` | direct_file | curl |
| `magnet:?xt=urn:btih:*` | magnet | aria2c |
| `https://*.torrent` | torrent | aria2c |
| `https://alfafile.net/file/*` / `https://nitroflare.com/view/*` | unknown | curl（但很可能进不了真下载页——见 `references/anti-bot.md`） |

## Windows 特殊约定

- `uv tool install <pkg>` 装到 `%LOCALAPPDATA%\.local\bin`（即 `~/.local/bin`）。
- **每次 `terminal` 调用是新 shell**，找不到工具时必须显式：
  ```bash
  export PATH="$HOME/.local/bin:$PATH" && yt-dlp --version
  ```
- `winget install -e --id aria2.aria2` 装完二进制在 `%LOCALAPPDATA%\\Microsoft\\WinGet\\Links\\`，PATH 里通常已有。
- **不要试图 `pip install yt-dlp`**：`pip` 不在 PATH，`uv tool install` 才是正确的安装方式。

## Linux / macOS 特殊约定

- Linux: `apt install aria2` 或 `dnf install aria2`；yt-dlp 用 `uv tool install` 或 `pipx install yt-dlp`。
- macOS: `brew install aria2 yt-dlp`（一条命令两个都装）。

## 何时向用户询问安装

**任何工具缺失时都要问，绝不静默安装。**询问内容包含：
1. 要装哪个工具（名字）
2. 为什么需要（这个 URL 类型没有别的替代）
3. 用哪个包管理器（本机探测：Windows → winget；Linux → apt/dnf；macOS → brew）
4. 大约多大（体积）
5. 一句"go"才能装

示例询问文案：
> 「这个链接需要 yt-dlp 才能下载（YouTube 页面直接 curl 拿不到视频流）。要用 uv 装吗？大约 3 MB，命令是 `uv tool install yt-dlp`。回复"go"我就装。」
