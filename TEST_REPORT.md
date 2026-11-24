# 测试报告

## v0.5.0 SQLite 媒体库索引

- 四项 Python 定向用例：剧级/单集/电影独立判定，NFO 缺图仍已刮削，NFO 缓存与文件/图片变化，移除标记、离线或空挂载保留索引，拒绝 XML 实体，前缀边界、最长匹配及管理员接口合同。使用项目忽略目录内的临时文件和独立数据库，未读取用户库。
- 两项 Vue 用例：状态与路径详情、目录浏览、仅手动启动扫描、实例 API 范围、前缀转换及设置预览。
- 实际联邦构建以 Mock API 完成设置→媒体库→手动模拟扫描→展开缺图详情。TypeScript、生产构建、官方版本与联邦 CSS 门禁通过，发布包排除运行数据库。未操作用户 MP/CMS、真实媒体库或刮削功能。
- 第一阶段仅索引和路径预览，分享同步仍使用既有固定目录。实际挂载、权限、规模与真实 NFO 兼容性待用户实机验证。

## v0.4.0 CMS 分享同步

- 三项 Python 定向测试通过：演练零上游调用、非法路径和越权字段被拒绝、提交契约、只读验证失败不发送、明确拒绝可人工重试、受理和未知状态不重发、插件重建后的防重记录及落盘脱敏。CMS 全部使用 Mock。
- 三项 Vue 用例通过：保存设置及拒绝 Cookie、兼容旧配置、一键提交只携带候选编号且未知结果禁用重复操作。使用实际联邦产物在本机浏览器保存模拟设置，点击结果行「演练同步」显示行内回执。TypeScript、生产构建、版本与联邦 CSS 门禁通过。
- 未调用真实 CMS，未操作用户 MoviePilot 实例。内部接口实机兼容性及 STRM 生成待用户自行验证。

## v0.3.1 弹窗居中与重复记录

- 两项定向 Vue 用例通过，覆盖重复项折叠、展开、收起、不重发搜索及现有的提取码冲突保护。一项 Python 用例通过，覆盖跨域名同码、原始/分组来源、显示上限与替代提取码不出现在重复记录中。
- 本机浏览器加载生产联邦产物，以演示数据确认展开后新增记录位于所属分享下，弹窗中心与视口中心在 1px 内对齐。类型检查、生产构建、官方版本及联邦 CSS 门禁通过。未操作用户的 MoviePilot 或发起真实搜索。

## v0.3.0 TheMovieDb 搜索页

- 两项定向 Vue 用例通过：电影/剧集与排序、风格、语言、最低评分参数；片名查询限定 TMDB 来源，点海报将片名和年份交给当前插件实例的 PanSou 接口，关闭弹窗保留列表。
- 一项 Python 菜单、版本与接口合同用例通过。类型检查、生产构建、官方版本及联邦 CSS 门禁通过。
- 本机浏览器以真实生产 `./AppPage` 联邦构建和模拟宿主 API 显示筛选和海报，点击《钢铁侠》自动填 2008 年并显示两条紧凑的模拟分享。未访问 MP 实例或做真实搜索；真实菜单显示和实际查询待用户实机验证。

集成依据：[MoviePilot 官方侧栏注册指南](https://github.com/jxxghp/MoviePilot-Plugins/blob/main/docs/faq/17-register-plugin-sidebar-nav.md)、[原生 TMDB 浏览实现](https://github.com/jxxghp/MoviePilot-Frontend/blob/v3/src/views/discover/TheMovieDbView.vue)、[宿主媒体搜索](https://github.com/jxxghp/MoviePilot/blob/v3/app/api/endpoints/media.py)。

## v0.2.1 紧凑结果列表

- 本轮仅改结果页布局和版本元数据：收起时每条 48 CSS px，左侧两行文字，右侧为详情、复制和打开；完整标题、链接和提取码按需展开。
- 仅运行相关的两个 Vue 用例，均通过；类型检查、生产构建、官方版本与联邦 CSS 门禁及本地打包通过。使用真实联邦构建和虚构数据在本机浏览器查看新横条，未触及 MP 实例、PanSou 或 CMS。

## v0.2.0 搜索版测试报告

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
