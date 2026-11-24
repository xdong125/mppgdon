# mppgdon

xdong125 的 MoviePilot V3 插件仓库。当前版本：**MPPGDON 网盘搜索 v0.5.0**。

## 更新与使用

1. MP 插件市场仓库配置追加 `https://github.com/xdong125/mppgdon`，保留已有仓库地址（`PLUGIN_MARKET` 多地址以英文逗号分隔）。
2. 已安装 v0.1.0 的用户直接更新原“MPPGDON 安装测试”插件；插件 ID 仍为 `MppgdonTest`，更新后名称变为“MPPGDON 网盘搜索”。无需卸载重装。
3. 在配置页启用插件，保存 PanSou 服务地址。默认 `https://pansou.tiandechi.com`；此公开服务通常无需 Token。自己的服务有认证时填写 PanSou Token，可含 Bearer 前缀。
4. 更新并启用后刷新 MP 网页，从左侧「发现 → TheMovieDb 网盘搜索」进入。可按电影/电视剧、排序、风格、原始语言与最低评分浏览，也可单独按片名查找。沿用 MP 自己的 TMDB 连接，无需在插件里填密钥。
5. 点击海报或其右下角「搜网盘」，在当前页面弹窗按片名和有记录的年份自动搜索 115；关闭后保留筛选位置。顶部「网盘搜索」标签与原插件详情继续支持手工搜索，可选年份和清晰度。
6. 网盘结果按双行横条显示，右侧提供详情、复制和打开；浏览器不允许自动复制时，点击详情后手动复制。
7. 结果统计旁的「展开重复」会在同一分享下列出被合并的标题、来源、时间和画质，不重新发起搜索。重复记录不是额外的独立分享；每个分享最多列出 30 条，重复次数仍按全部命中记录统计。

本版只搜索 **115 分享**，合并 PanSou 原始/分组响应并按分享标识去重。未标注年份的标题不会仅因年份筛选被排除；画质、季集均来自标题。链接有效性及实际内容仍需自行核对。提取码冲突会提示并禁用复制/打开快捷操作。搜索结果仅保留在当前页面，不写入宿主媒体数据。

## CMS 分享同步

1. 用 MoviePilot 超级管理员账号打开插件「连接设置 → CMS 分享同步」。填 MP 容器能访问的 CMS 根地址、CMS 网页登录后的 `Authorization: Bearer …`（可只填 Token）、CMS 容器内的具体 STRM 目录，例如 `/media/网盘影视`，以及分享目录 CID。CID `0` 表示整个分享。此功能不读 Cookie，也不需要用于转存的 `CMS_API_TOKEN`。
2. 保存后重新打开搜索页并搜索。默认按钮是「演练同步」，不会请求 CMS。确认目录及同步范围后，在插件设置勾选「启用真实提交」并保存，重新搜索后点击结果行的「分享同步」。不需要再次填写地址或目录。
3. 看到「CMS 已受理」后，到 CMS 和目标目录核对 STRM。若提示「待核实」，不要重复提交；插件会保留同一分享、CMS、CID 和目录的防重记录，重启后也有效。记录只存摘要和状态，不存登录 Token 或提取码。防重不与其他客户端共享。

插件只在用户点击后调用 CMS 当前网页使用的内部分享同步接口，并先做只读验证，不保存 CMS 全局配置，不执行公开 API 转存，不创建定时任务。CMS 升级后需复核内部接口兼容性。登录 Token 存在 MoviePilot 的插件设置中，不出现在搜索或状态响应；不要公开插件配置或备份。优先使用可信网络上的 HTTPS。

## 媒体库索引

1. 超级管理员在插件设置的「媒体库索引」中填电影根目录、电视剧根目录，使用 MP 容器实际能读取的路径。允许先填其中一个，两个目录不能互相包含。
2. 可选填写 `MP前缀#CMS前缀`，一行一条，例如 `/mnt/media#/media`。规则按目录边界匹配，多个匹配时取最长前缀；空规则保持原路径。设置提供实时转换预览，索引详情也列出 MP/CMS 两种路径。
3. 保存后刷新网页，进入「TheMovieDb 网盘搜索 → 媒体库」点「扫描媒体库」。可按片名/路径、类型、文件类别和刮削状态查询；点根目录或子目录浏览文件层级。列表每页 50 条。
4. 电影和单集按同名有效 NFO 判断（电影兼容 `movie.nfo`），剧级单独检查 `tvshow.nfo`。有效要求 XML 可解析、对应根标签和非空标题。缺图仍算已刮削，另记海报/背景/标志图或单集缩略图缺失；图片存在只按文件名和非零大小判断，不检查画质或解码结果。

索引独立保存为插件数据目录下的 `media-library.sqlite3`（原 CMS 防重库保留）。只记录路径、文件属性和有限 NFO 字段；不读取 STRM 播放地址或媒体内容。再次扫描仍列举文件以发现变化，但文件大小和修改时间未变的 NFO 不重新解析。目录未挂载、读取失败或旧根目录突然变空时保留原索引并提示异常；成功完成根目录扫描后才标记已移除文件。

**此版完成第一阶段：索引、扫描和路径映射预览。** 尚未按索引自动改变分享同步目录，也不创建媒体目录或触发 MP 刮削；CMS 仍使用原来的固定 STRM 目录。后续按剧名/S01 和电影名 (年份) 自动选目录、处理多季合集另行实现。索引结构和恢复规则见 [LIBRARY_INDEX.md](LIBRARY_INDEX.md)。

## 分发方式

支持 MoviePilot `>=3.0.0,<4`，使用 `main` 分支的 `package.v3.json`。插件使用官方 Vue 联邦方式，完整构建产物位于 `dist/assets`，`release: true`；GitHub Actions 将运行源码和产物打包为 `MppgdonTest_v0.5.0` Release 中的 `mppgdontest_v0.5.0.zip`。MP 安装器自动下载，无需手工上传文件。

若更新后仍显示旧页面，请刷新 MP 浏览器页面。若没有新菜单，确认插件已启用、账户有搜索权限；菜单不替换 MP 原生「探索」。无法发现更新时先刷新市场，检查 MP 到 GitHub API / raw.githubusercontent.com / Releases 下载域名的连接。默认第三方 PanSou 的可用性不由本仓库保证，可在配置中更换服务根地址。

## 开发与验证

- Python 无新增依赖，复用宿主 `app.sdk.plugin`、`app.sdk.network`、`schemas.Response` 与 Pydantic。
- 前端位于 `frontend/`，使用 Node.js 22.12+（已测试 Node 24）：`npm ci --ignore-scripts`、`npm run typecheck`、`npm test`、`npm run build`。
- 后端回归：在宿主 Python 环境运行 `python tests/v3/mppgdontest/test_plugin.py -v`；测试用 Mock 替换宿主和上游边界。
- 本地页面预览：`npm run preview:local`。查询使用演示数据，海报来自 TMDB 图片服务；不会访问 MP、CMS 或真实分享。
- 发布前运行官方版本门禁、联邦 CSS 门禁和 `git diff --check`；通过本地 Git commit/push 发布，不使用网页逐文件上传。

依据：[官方 V3 手册](https://github.com/jxxghp/MoviePilot-Plugins/blob/main/docs/Plugin_Development.md)、[V3 API 响应约定](https://github.com/jxxghp/MoviePilot-Plugins/blob/main/docs/V3_API_Response_Adaptation.md)、[前端联邦指南](https://github.com/jxxghp/MoviePilot-Frontend/blob/v3/docs/module-federation-guide.md)、[PanSou API](https://github.com/fish2018/pansou#api文档)。测试结果与证据边界见 [TEST_REPORT.md](TEST_REPORT.md)。
