# mppgdon

xdong125 的 MoviePilot V3 插件仓库。当前提供 **MPPGDON 安装测试 v0.1.0**。

## 安装测试

1. 在 MoviePilot 的插件市场仓库配置中追加 `https://github.com/xdong125/mppgdon`。若通过环境变量 `PLUGIN_MARKET` 配置，保留已有仓库，多个地址用英文逗号分隔。
2. 刷新插件市场，搜索 **MPPGDON 安装测试**，点击安装。
3. 打开插件配置，开启“启用测试插件”，把展示文本改为“我的 MP 插件安装成功”，保存。
4. 打开插件详情页，应看到版本 `0.1.0`、状态“已启用”以及刚保存的文本。
5. 刷新页面或重启 MP 后再查看，确认配置保留；关闭启用开关并保存，确认状态变为“已停用”。

仓库使用 `main` 分支。测试版采用源码文件列表安装（`release: false`），不需要手工下载 ZIP。仅支持 MoviePilot `>=3.0.0,<4`。

本插件只显示配置文本，没有第三方依赖、网络请求、定时任务、CMS 对接或媒体文件操作。不会自动验证 STRM 播放或触发转存。

## 开发依据

- [官方 V3 开发手册](https://github.com/jxxghp/MoviePilot-Plugins/blob/main/docs/Plugin_Development.md)
- [官方仓库与发布约定](https://github.com/jxxghp/MoviePilot-Plugins/blob/main/docs/Repository_Guide.md)
- 插件：`plugins.v3/mppgdontest/__init__.py`，主类/ID：`MppgdonTest`。
- 市场索引：`package.v3.json`；旧代索引为空，避免被 V1/V2 安装。
- 使用稳定 SDK `app.sdk.plugin._PluginBase` 与 Vuetify JSON 页面。

本地验证与真实宿主验证边界见 [TEST_REPORT.md](TEST_REPORT.md)。
