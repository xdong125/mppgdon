# v0.1.0 测试报告

日期：2026-11-24，目标 MoviePilot V3。

## 开发依据

已阅读官方 `docs/Plugin_Development.md`（V3 完整主指南）、`docs/Repository_Guide.md` 和仓库 README；并核对 MoviePilot `v3` 分支的 `app/sdk/plugin/base.py` 与 `app/adapters/system/plugin/package.py`。

- 开发指南 blob：`dd3a856cf4c5795562414f5fc5cd6a8b559a646a`。
- V3 基类 blob：`db38a184db0299d8356c3f94612797859f72eb4a`。
- 官方版本门禁脚本 blob：`1c96a90f31430d55b5037037b81ec19e2366cf77`。

## 本地结果

- Python 编译通过。
- 直接运行官方版本门禁脚本通过，索引、类版本、历史记录均为 `0.1.0`。
- 对照官方基类源码，6个抽象方法及其参数名均完整匹配。
- 7项单元测试全部通过：初始停用、配置展示、停用/重复初始化、实例隔离、普通文本页面、表单模型/空扩展、市场元数据一致性。
- 单元测试以生产模块名 `app.plugins.mppgdontest` 导入；宿主基类使用 Mock，仅验证插件自己的行为，不声称运行了完整宿主。
- `release: false` 与官方安装器源码文件列表分发路径一致。插件无额外依赖，无需前端构建。

本地运行命令：

```sh
python -m compileall plugins.v3/mppgdontest
python tests/v3/mppgdontest/test_plugin.py -v
```

## 待用户实机验证

当前未连接或操作用户 MoviePilot，因此市场发现、实际安装、配置持久化、真实详情页渲染及重启后加载仍待用户测试。安装步骤见 README。出现问题时需要 MP 的完整 V3 版本号和脱敏错误日志；无需提供密码或 Token。
