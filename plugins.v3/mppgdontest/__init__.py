"""MoviePilot V3 的 PanSou 网盘搜索入口。"""

import asyncio
import json
import sqlite3
import threading

from fastapi import Depends

from app import schemas
from app.api.dependencies.auth import get_current_active_superuser
from app.sdk.network import RequestUtils
from app.sdk.plugin import _PluginBase

from .search import DEFAULT_URL, SearchData, SearchError, SearchRequest, StatusData, normalize_base, normalize_results
from .share_sync import ShareSync, SyncConfig, SyncRequest, SyncResult
from .library import LibraryConfig, LibraryIndex, LibraryView
from .routing import TargetResolver


class MppgdonTest(_PluginBase):
    """保留测试版插件 ID，原位升级为用户主动操作的搜索插件。"""

    plugin_name = "MPPGDON 网盘搜索"
    plugin_desc = "通过 PanSou 搜索、筛选和去重 115 分享资源。"
    plugin_icon = "https://raw.githubusercontent.com/jxxghp/MoviePilot-Plugins/main/icons/Moviepilot_A.png"
    plugin_version = "0.6.0"
    plugin_author = "xdong125"
    author_url = "https://github.com/xdong125"
    plugin_config_prefix = "mppgdontest_"
    plugin_order = 50
    auth_level = 1
    _enabled = False
    _base = DEFAULT_URL
    _token = ""
    _config_error = ""
    _sync = None
    _sync_error = ""

    def init_plugin(self, config: dict | None = None) -> None:
        """加载连接配置；初始化和重载均不主动搜索。"""
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._config_error = ""
        self._token = str(config.get("pansou_token") or "").strip()
        if self._token.lower().startswith("bearer "):
            self._token = self._token[7:].strip()
        try:
            self._base = normalize_base(config.get("pansou_url") or DEFAULT_URL)
            if any(ord(c) < 32 or ord(c) > 126 for c in self._token):
                raise SearchError("PanSou Token 格式错误，请重新填写。")
        except SearchError as error:
            self._config_error = str(error)
        if not hasattr(self, "_search_lock"):
            self._search_lock = threading.Lock()
        if not hasattr(self, '_library'):
            self._library = LibraryIndex(lambda: self.get_data_path())
        self._library_config = LibraryConfig((), ())
        self._library_error = ''
        try:
            self._library_config = LibraryConfig.from_settings(config)
        except SearchError as error:
            self._library_error = str(error)
        self._sync = None
        self._sync_error = ''
        try:
            sync = SyncConfig.from_settings(config)
            if sync:
                if self._library_error or not self._library_config.roots:
                    raise SearchError(self._library_error or '请先配置电影或电视剧根目录。')
                self._sync = ShareSync(sync, self.get_data_path, TargetResolver(self._library_config, self._library))
        except SearchError as error:
            self._sync_error = str(error)

    def get_state(self) -> bool:
        """返回用户设置的插件启用状态。"""
        return self._enabled

    @staticmethod
    def get_command() -> list[dict]:
        """搜索通过插件页面发起，不注册消息命令。"""
        return []

    @staticmethod
    def get_render_mode() -> tuple[str, str]:
        """使用宿主加载的 Vue 联邦页面。"""
        return "vue", "dist/assets"

    @staticmethod
    def get_sidebar_nav() -> list[dict]:
        """通过宿主导航注册独立页面，不修改原生探索。"""
        return [{"nav_key": "main", "title": "发现",
                 "icon": "mdi-movie-search-outline", "section": "discovery",
                 "permission": "search", "order": 30}]

    def get_api(self) -> list[dict]:
        """注册带宿主 Bearer 鉴权和具体响应模型的接口。"""
        return [
            {"path": "/status", "endpoint": self.get_status, "methods": ["GET"],
             "auth": "bear", "summary": "网盘搜索状态",
             "response_model": schemas.Response[StatusData]},
            {"path": "/search", "endpoint": self.search, "methods": ["POST"],
             "auth": "bear", "summary": "搜索 PanSou 115 分享",
             "response_model": schemas.Response[SearchData]},
            {"path": "/share-sync", "endpoint": self.submit_share_sync, "methods": ["POST"],
             "auth": "bear", "summary": "管理员手动提交 CMS 分享同步",
             "response_model": schemas.Response[SyncResult]},
            {"path": "/library", "endpoint": self.library_view, "methods": ["GET"],
             "auth": "bear", "summary": "管理员查看本地媒体库索引",
             "response_model": schemas.Response[LibraryView]},
            {"path": "/library/scan", "endpoint": self.library_scan, "methods": ["POST"],
             "auth": "bear", "summary": "管理员手动扫描已配置的媒体根目录",
             "response_model": schemas.Response[LibraryView]},
        ]

    async def library_view(
        self, page: int = 1, keyword: str = '', kind: str = '', entry_type: str = 'media',
        scrape: str = '', parent: str = '', include_missing: bool = False,
        _admin=Depends(get_current_active_superuser),
    ) -> schemas.Response[LibraryView]:
        if (not 1 <= page <= 100000 or len(keyword) > 120 or len(parent) > 4096
                or kind not in ('', 'movie', 'tv') or entry_type not in ('', 'directory', 'media', 'nfo', 'image', 'other')
                or scrape not in ('', 'scraped', 'not_scraped', 'incomplete')):
            return schemas.Response(success=False, message='索引筛选参数无效。')
        if self._library_error:
            return schemas.Response(success=True, data=LibraryView(config_error=self._library_error))
        try:
            view = await asyncio.to_thread(self._library.view, self._library_config, page=page, keyword=keyword,
                                          kind=kind, entry_type=entry_type, scrape=scrape, parent=parent,
                                          include_missing=include_missing)
            return schemas.Response(success=True, data=view)
        except (OSError, sqlite3.Error):
            return schemas.Response(success=False, message='无法读取插件媒体索引，请检查插件数据目录权限。')

    async def library_scan(self, _admin=Depends(get_current_active_superuser)) -> schemas.Response[LibraryView]:
        if not self._enabled or self._library_error:
            return schemas.Response(success=False, message=self._library_error or '请先启用插件。')
        try:
            self._library.start(self._library_config)
            return schemas.Response(success=True, message='扫描已启动，只读媒体目录。', data=LibraryView())
        except SearchError as error:
            return schemas.Response(success=False, message=str(error))
        except (OSError, sqlite3.Error):
            return schemas.Response(success=False, message='无法启动扫描，请检查插件数据目录权限。')

    def get_status(self) -> schemas.Response[StatusData]:
        """仅返回可公开的连接状态，不返回上游 Token。"""
        return schemas.Response(success=True, message="", data=StatusData(
            enabled=self._enabled, version=self.plugin_version,
            pansou_url=self._base, token_set=bool(self._token), config_error=self._config_error,
            sync_mode=("live" if self._sync.config.live else "dry_run") if self._enabled and self._sync else "unavailable",
            sync_error=self._sync_error,
        ))

    async def submit_share_sync(
        self, payload: SyncRequest, _admin=Depends(get_current_active_superuser),
    ) -> schemas.Response[SyncResult]:
        sync = self._sync
        if not self._enabled or sync is None:
            return schemas.Response(success=True, data=SyncResult(status="not_sent"),
                                    message=self._sync_error or "请先启用插件并保存 CMS 分享同步设置。")
        result, message = await asyncio.to_thread(sync.submit, payload.ticket)
        return schemas.Response(success=True, data=result, message=message)

    async def search(self, payload: SearchRequest) -> schemas.Response[SearchData]:
        """在请求生命周期内搜索，不阻塞宿主异步事件循环。"""
        if not self._enabled:
            return schemas.Response(success=False, message="请先在配置中启用插件并保存。")
        if self._config_error:
            return schemas.Response(success=False, message=self._config_error)
        base, token, sync = self._base, self._token, self._sync

        def run_search():
            """由工作线程持有锁，客户端取消也不提前开放第二次请求。"""
            if not self._search_lock.acquire(blocking=False):
                raise SearchError("已有搜索正在进行，请等待完成。")
            try:
                return self._search_sync(payload, base, token)
            finally:
                self._search_lock.release()

        try:
            data = await asyncio.to_thread(run_search)
            if sync is not None and sync is self._sync:
                await asyncio.to_thread(sync.add_tickets, data, payload)
            return schemas.Response(success=True, message="", data=data)
        except SearchError as error:
            return schemas.Response(success=False, message=str(error))

    @staticmethod
    def _search_sync(payload: SearchRequest, base: str, token: str) -> SearchData:
        """通过稳定网络 SDK 读取有界响应，拒绝重定向且不重试。"""
        headers = {"Accept": "application/json", "Content-Type": "application/json",
                   "User-Agent": "MoviePilot-Mppgdon/0.6.0"}
        if token:
            headers["Authorization"] = "Bearer " + token
        client = RequestUtils(headers=headers, timeout=35, verify=True)
        response = None
        try:
            response = client.post_res(
                base + "/api/search",
                json={"kw": payload.keyword, "res": "all", "src": "all", "refresh": False,
                      "cloud_types": ["115"], "conc": 1,
                      "filter": {"exclude": ["预告", "花絮"]}},
                allow_redirects=False, stream=True,
            )
            if response is None:
                raise SearchError("PanSou 搜索超时或网络连接失败，未自动重试。")
            if not 200 <= response.status_code < 300:
                if 300 <= response.status_code < 400:
                    raise SearchError("PanSou 返回重定向，请填写最终服务地址。")
                raise SearchError(f"PanSou HTTP {response.status_code}，请检查服务、认证或限流。")
            content = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                content.extend(chunk)
                if len(content) > 8 * 1024 * 1024:
                    raise SearchError("PanSou 响应过大，请缩小搜索范围。")
            raw = json.loads(content.decode("utf-8-sig", errors="replace"))
            return normalize_results(raw, payload)
        except OSError:
            raise SearchError("PanSou 搜索超时或网络连接失败，未自动重试。") from None
        except (ValueError, UnicodeError):
            raise SearchError("PanSou 未返回有效 JSON，请检查服务地址。") from None
        finally:
            if response is not None:
                response.close()
            client.close()

    def get_form(self) -> tuple[None, dict]:
        """为 Vue 配置页提供默认值；旧版 enabled 配置继续生效。"""
        return None, {"enabled": False, "pansou_url": DEFAULT_URL, "pansou_token": "",
                      "cms_url": "", "cms_login_token": "",
                      "cms_sync_cid": "0", "cms_sync_live": False,
                      "library_movie_root": "", "library_tv_root": "", "library_path_mapping": ""}

    def get_page(self) -> list:
        """详情页由联邦 Page 组件渲染。"""
        return []

    def stop_service(self) -> None:
        """停止接收新请求；不取消已经发出的 CMS 提交。"""
        self._enabled = False
        self._sync = None
        if hasattr(self, '_library'):
            self._library.stop()
