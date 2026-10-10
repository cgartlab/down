# URL 探测器（detect.py）

`scripts/detect.py` 是本 skill 的核心探测器：给定一个 URL，返回 JSON 描述 URL 类型、建议工具、目标文件名和验证命令。

## 契约

**输入**：`--url <url>`（必填）

**输出（stdout）**：JSON，字段：

| 字段 | 类型 | 含义 |
|------|------|------|
| `url` | str | 原样回传 |
| `host` | str | 域名（`urlparse().hostname`），可能为空（如 `magnet:`） |
| `kind` | str | `platform_video` / `direct_file` / `torrent` / `magnet` / `unknown` |
| `suggested_tool` | str | `yt-dlp` / `curl` / `aria2c` |
| `dest_name` | str | 建议的目标文件名（含扩展名），caller 决定最终路径 |
| `verify_cmd` | str | 验证命令模板（含 `<file>` 占位符） |
| `install_hint` | dict | 建议工具缺失时的安装提示，可能为空 `{}` |

**退出码**：0（除 --help/参数错误外永不非零——错误信息走 JSON）

## 判定优先级（从上到下短路）

1. URI scheme 是 `magnet:` → `kind=magnet`
2. 路径以 `.torrent` 结尾 → `kind=torrent`
3. host 在 `PLATFORM_SITES` 白名单里 → `kind=platform_video`
4. 路径有扩展名且是视频/音频/图片/归档/文档 → `kind=direct_file`
5. 都不匹配 → `kind=unknown`

## 平台站白名单（PLATFORM_SITES）

当前覆盖：`youtube.com`, `youtubekids.com`, `youtu.be`, `music.youtube.com`, `twitter.com`, `x.com`, `bilibili.com`, `b23.tv`, `tiktok.com`, `vm.tiktok.com`, `vimeo.com`, `dailymotion.com`, `douyin.com`, `weibo.com`, `redditmedia.com`, `reddit.com`, `twitch.tv`

**新增站点**：在 `scripts/detect.py` 顶部 `PLATFORM_SITES` 字典加一行，值统一 `"yt-dlp"`。

## 文件名生成规则

- **平台视频**：`<host>_<id>.<ext>`，id 从 URL 提取
  - YouTube `?v=<id>` → `www_youtube_com_<id>.mp4`
  - X/Twitter `/status/<id>/video/*` → `x_com_<id>.mp4`
  - youtu.be 短链 `/youtu.be/<id>` → `youtube_<id>.mp4`
- **直链文件**：直接取路径末段（URL decode `%20` → 空格）
- **magnet**：从 `dn=` 参数取（URL decode）

## 验证命令模板

- 媒体文件（视频/音频）→ `ffprobe`
- 归档/文档/图片/其他 → `file`

`<file>` 占位符在 SKILL.md 的 Phase 4 被 caller 替换为真实绝对路径。

## 反例：不做网络请求

探测器**不发送任何 HTTP 请求**。原因：
1. 有些站点的 Referer/User-Agent 会泄露用户身份，探测即触发反爬。
2. `curl -I` 对某些 CDN 会返回 `302 → challenge page`，把简单直链误判为 unknown。
3. 用户可能希望"探测 + 询问"是一次轻量对话，而不是偷偷去访问目标服务器。

**如果 caller 需要对 unknown URL 做进一步网络判定**，由 caller 决定（例如 curl -I 看 Content-Type），detect.py 只返回元数据不代替决策。

## 测试

`evals/test_detect.py` 覆盖：
- 每个 kind 至少 1 个 URL
- YouTube `?v=` 与 youtu.be 短链的 id 提取
- X/Twitter status id 提取
- magnet `dn=` 参数解析
- 路径无扩展名但 host 是 .com/.org 的 unknown 兜底
- 空 URL / 畸形 URL 的错误处理
