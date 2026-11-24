# v0.2.0 搜索版测试报告

日期：2026-11-24。目标 MoviePilot V3，插件 ID 继续使用 MppgdonTest。

## 本地验证

- Python 后端15项测试全部通过：两种PanSou响应/业务包装、115去重、年份画质筛选、非法域名/协议/提取码、密码缺失补充/冲突、空结果与错误区分、请求验证、SDK请求参数及证书校验、响应关闭、鉴权声明、Token脱敏、HTTP/超时/无效JSON/过大响应、重复初始化和取消后的并发保护。
- Vue 前端7项组件测试全部通过：当前实例API作用域、三字段envelope、文本转义、空输入/年份验证、失败与空结果区分、防重复及网络失败不重试、提取码冲突、旧配置保留与URL校验。
- vue-tsc类型检查、Vite生产构建、Python编译、官方check_plugin_versions.py、官方check_federation_css.py和git diff --check均通过。
- Release生成脚本成功生成mppgdontest_v0.2.0.zip，包含Python源码与完整dist/assets/remoteEntry.js及其所有分块，不含测试、node_modules或本地数据。
- 浏览器已加载实际生产remoteEntry.js（模拟宿主提供共享Vue），成功渲染搜索界面和虚构结果卡片。该检查验证真实联邦产物，数据/API仍为Mock，不能当成真实MP宿主联调。

验证命令：

```sh
python tests/v3/mppgdontest/test_plugin.py -v
python -m compileall plugins.v3/mppgdontest
cd frontend
npm run typecheck
npm test
npm run build
# 返回仓库根目录后生成正式安装包
python scripts/release.py
```

SDK网络边界使用Mock，测试不调用CMS、转存、下载器或用户媒体库。网络请求使用固定/api/search，cloud_types=["115"]，verify=True，禁用重定向和自动重试；响应按流限制8MiB。所有输出模型明确声明，Token不出现在status/search响应。

## 真实环境证据与限制

- v0.1.0：用户已明确反馈“安装成功了”，仅证明此前最小测试版能安装。
- v0.2.0：开发机向用户指定PanSou服务进行一次只读真实搜索，结果超时；随后一次只读健康检查也未能连接。没有将失败标为空结果，没有自动重试，没有声称本轮真实搜索成功。
- 当前不把开发机到第三方服务的失败推广为MP端必然失败。MP容器的DNS、代理、证书及第三方服务状态需用户实测；服务地址可在插件中更换。
- 新版在用户MP中的更新、Vue宿主加载、认证、实际搜索及复制行为尚待用户验证。未操作用户MP，也未重启或修改CMS工作台。

## 开发依据

已读取官方V3开发指南、仓库/发布指南、API响应专题、V3前端联邦指南、PageRender/FormRender、宿主RequestUtils实现以及PanSou官方API文档。

- 使用plugins.v3与package.v3.json，继承app.sdk.plugin._PluginBase。
- 通过app.sdk.network.RequestUtils发送搜索；API使用宿主Bearer和schemas.Response[具体数据模型]。
- 联邦Page/Config复用宿主注入api和当前pluginId；无Vuetify/MDI全局样式。
- 发布配置release=true，GitHub Actions打包固定版本资产；开发和发布均通过本地Git提交/推送。
