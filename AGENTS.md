# 开发与发布约定

- 本仓库为 xdong125/mppgdon，目标 MoviePilot V3。
- 先阅读官方 V3 插件开发手册与仓库指南；新插件放入 plugins.v3，索引为 package.v3.json。
- 使用本地 Git 工作副本开发、检查、提交和推送；不使用 GitHub 网页逐文件发布。
- 推送前检查 git status、diff、版本一致性并运行相关测试；只提交本任务文件。
- 修改插件实现时同步 plugin_version、市场索引 version 和 history。纯文档反馈更新无需提高插件版本。
- 不提交凭据、本地配置、运行数据或 __pycache__。
- 当前测试入口与验证边界见 README.md 和 TEST_REPORT.md；用户已确认 v0.1.0 安装成功。
