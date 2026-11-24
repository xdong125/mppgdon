# 开发与发布约定

- 本仓库为 xdong125/mppgdon，目标 MoviePilot V3。
- 先阅读官方 V3 插件开发手册与仓库指南；新插件放入 plugins.v3，索引为 package.v3.json。
- 使用本地 Git 工作副本开发、检查、提交和推送；不使用 GitHub 网页逐文件发布。
- 推送前检查 git status、diff、版本一致性并运行相关测试；只提交本任务文件。
- 修改插件实现时同步 plugin_version、市场索引 version 和 history。纯文档反馈更新无需提高插件版本。
- 不提交凭据、本地配置、运行数据或 __pycache__。
- 当前入口与验证边界见 README.md、TEST_REPORT.md，媒体库与自动目录约定见 [LIBRARY_INDEX.md](LIBRARY_INDEX.md)。v0.6.0 根据根目录、索引和身份/季号自动生成同步目标，移除固定路径；真实提交才允许创建目标目录，不触发刮削。
- 回归范围按实际改动收敛；纯界面调整只做相关前端验证和发布门禁，不重复运行无关后端用例或真实环境测试。

- 当前ID继续使用MppgdonTest以原位更新，展示名为MPPGDON网盘搜索。Vue页面源码frontend/，完整构建产物提交plugins.v3/mppgdontest/dist/assets；必须通过官方联邦CSS门禁。
- 仅搜索115；用户已明确授权手动分享同步和 CMS 官方 API 转存，两者默认演练、真实开关与 Token 独立，只有用户开启后主动点击才提交。开发仅用 Mock，不改 CMS 全局配置或引入后台轮询。受理/未知保持持久防重，明确拒绝后人工重试；测试期不加次数/等待限制。发布前确认对应 GitHub Release 及 ZIP 资产已生成。
- 媒体库仅在用户手动点扫描后运行一次；页面可查询本次扫描进度，无无人值守扫描。独立 SQLite 不存 STRM 内容、凭据或原始 NFO，不跟随符号链接。NFO 与图片分别判定，缺图仍算已刮削。路径映射仅前缀边界替换，索引以 MP 路径为准。
