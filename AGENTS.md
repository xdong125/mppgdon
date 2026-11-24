# 开发与发布约定

- 本仓库为 xdong125/mppgdon，目标 MoviePilot V3。
- 先阅读官方 V3 插件开发手册与仓库指南；新插件放入 plugins.v3，索引为 package.v3.json。
- 使用本地 Git 工作副本开发、检查、提交和推送；不使用 GitHub 网页逐文件发布。
- 推送前检查 git status、diff、版本一致性并运行相关测试；只提交本任务文件。
- 修改插件实现时同步 plugin_version、市场索引 version 和 history。纯文档反馈更新无需提高插件版本。
- 不提交凭据、本地配置、运行数据或 __pycache__。
- 当前搜索入口与验证边界见 README.md 和 TEST_REPORT.md。v0.4.0 增加 CMS 分享同步；插件改动不触碰独立工作台或用户的 CMS 实例。
- 回归范围按实际改动收敛；纯界面调整只做相关前端验证和发布门禁，不重复运行无关后端用例或真实环境测试。

- 当前ID继续使用MppgdonTest以原位更新，展示名为MPPGDON网盘搜索。Vue页面源码frontend/，完整构建产物提交plugins.v3/mppgdontest/dist/assets；必须通过官方联邦CSS门禁。
- 仅搜索115；用户已明确授权手动分享同步，默认演练，只有用户启用后主动点击才真实提交。开发仅用 Mock，不改 CMS 全局配置、不引入公开 API 转存或后台轮询。发布版本时需确认对应 GitHub Release 及 ZIP 资产已生成，再向用户交付更新。
