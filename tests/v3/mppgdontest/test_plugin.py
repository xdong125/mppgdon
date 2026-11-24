"""隔离宿主依赖的搜索测试；不冒充真实 MP 加载结果。"""

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from typing import Generic, TypeVar
from unittest.mock import MagicMock, patch

from pydantic import BaseModel, ValidationError

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "plugins.v3/mppgdontest/__init__.py"
T = TypeVar("T")


class Response(BaseModel, Generic[T]):
    """模拟宿主三字段响应模型，业务逻辑仍执行实际插件代码。"""

    success: bool
    message: str = ""
    data: T | None = None


def load_plugin():
    """从生产命名空间加载插件，替换数据库基类和网络 SDK 边界。"""
    modules = {name: types.ModuleType(name) for name in ["app", "app.plugins", "app.sdk", "app.sdk.plugin", "app.sdk.network", "app.schemas", "app.api.dependencies.auth", "fastapi"]}
    modules["app.sdk.plugin"]._PluginBase = type("_PluginBase", (), {})
    modules["app.sdk.network"].RequestUtils = MagicMock()
    modules["app.schemas"].Response = Response
    modules["app"].schemas = modules["app.schemas"]
    modules["app.api.dependencies.auth"].get_current_active_superuser = lambda: None
    modules["fastapi"].Depends = lambda dependency: dependency
    name = "app.plugins.mppgdontest"
    spec = importlib.util.spec_from_file_location(name, SOURCE, submodule_search_locations=[str(SOURCE.parent)])
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {**modules, name: module}):
        spec.loader.exec_module(module)
        search = sys.modules[name + ".search"]
        sync = sys.modules[name + ".share_sync"]
        library = sys.modules[name + ".library"]
    return module, search, sync, library


MODULE, SEARCH, SYNC, LIBRARY = load_plugin()


def fixture():
    """返回完全虚构的115分享数据，不包含用户分享。"""
    return {"merged_by_type": {"115": [
        {"note": "测试剧 (2026) S01E01 4K", "url": "https://115.com/s/example1?password=abcd"},
        {"note": "测试剧 (2026) S01E02 1080p", "url": "https://115cdn.com/s/example2"},
        {"note": "测试剧 (2025) 合集", "url": "https://115.com/s/oldyear"},
    ]}, "results": [{"title": "测试剧 (2026) S01E01 4K", "links": [
        {"type": "115", "url": "https://anxia.com/s/example1?password=abcd"},
        {"type": "quark", "url": "https://pan.quark.cn/s/example"},
    ]}]}


class SearchTests(unittest.TestCase):
    """验证结果转换、筛选、非法链接与提取码处理。"""

    def test_direct_and_enveloped_response(self):
        request = SEARCH.SearchRequest(keyword="测试剧")
        for payload in [fixture(), {"code": 200, "data": fixture()}, {"code": "200", "data": fixture()}]:
            result = SEARCH.normalize_results(payload, request)
            self.assertEqual(3, len(result.items))
            self.assertEqual(1, result.duplicates)

    def test_year_and_resolution(self):
        result = SEARCH.normalize_results(fixture(), SEARCH.SearchRequest(keyword="测试剧", year="2026", resolution="2160p"))
        self.assertEqual(["example1"], [i.id for i in result.items])
        self.assertEqual(2, result.filtered)
        self.assertEqual("S01E01", result.items[0].episode)

    def test_duplicate_metadata_preserves_origin_without_exposing_alternate_credentials(self):
        first = {"note": "测试剧 4K", "url": "https://115.com/s/example?password=primary"}
        grouped = dict(first, note="测试剧 4K 分组", source="plugin:fixture")
        raw = {"title": "测试剧 4K 原始", "channel": "fixture-channel", "datetime": "2026-11-24",
               "links": [{"type": "115", "url": "https://anxia.com/s/example?pwd=other"}]}
        payload = {"merged_by_type": {"115": [first, grouped]}, "results": [raw]}
        data = SEARCH.normalize_results(payload, SEARCH.SearchRequest(keyword="测试剧"))
        self.assertEqual(2, data.duplicates)
        [item] = data.items
        self.assertTrue(item.password_conflict)
        self.assertEqual("primary", item.password)
        self.assertEqual(
            [("grouped", "plugin:fixture", "测试剧 4K 分组"), ("raw", "fixture-channel", "测试剧 4K 原始")],
            [(row.origin, row.source, row.title) for row in item.duplicate_records],
        )
        self.assertEqual("2026-11-24", item.duplicate_records[1].published)
        self.assertNotIn("other", data.model_dump_json())

        payload["results"] *= SEARCH.MAX_DUPLICATES_PER_SHARE
        capped = SEARCH.normalize_results(payload, SEARCH.SearchRequest(keyword="测试剧"))
        self.assertEqual(SEARCH.MAX_DUPLICATES_PER_SHARE + 1, capped.duplicates)
        self.assertEqual(SEARCH.MAX_DUPLICATES_PER_SHARE, len(capped.items[0].duplicate_records))

    def test_bad_titles_and_urls_filtered(self):
        raw = {"merged_by_type": {"115": [
            {"note": title, "url": url} for title, url in [
                ("其他剧", "https://115.com/s/a"), ("测试剧 预告", "https://115.com/s/b"),
                ("测试剧", "https://115.com.evil.test/s/a"), ("测试剧", "javascript:alert(1)"),
                ("测试剧", "https://user:pass@115.com/s/c"), ("测试剧", "https://115.com:9000/s/d"),
            ]
        ]}}
        result = SEARCH.normalize_results(raw, SEARCH.SearchRequest(keyword="测试剧"))
        self.assertEqual([], result.items)
        self.assertEqual(6, result.filtered)

    def test_missing_password_is_enriched_and_conflict_flagged(self):
        raw = {"merged_by_type": {"115": [{"note": "测试剧", "url": "https://115.com/s/a" + suffix}
                for suffix in ["", "?password=abcd", "?password=efgh"]]}}
        result = SEARCH.normalize_results(raw, SEARCH.SearchRequest(keyword="测试剧"))
        self.assertEqual(1, len(result.items))
        self.assertTrue(result.items[0].password_conflict)
        self.assertEqual("abcd", result.items[0].password)

    def test_empty_is_success_invalid_structure_is_error(self):
        result = SEARCH.normalize_results({"results": []}, SEARCH.SearchRequest(keyword="测试剧"))
        self.assertEqual([], result.items)
        for payload in [{}, [], {"code": 401}, {"results": "bad"}, {"merged_by_type": {"115": None}}]:
            with self.subTest(payload=payload), self.assertRaises(SEARCH.SearchError):
                SEARCH.normalize_results(payload, SEARCH.SearchRequest(keyword="测试剧"))

    def test_request_validation(self):
        for data in [{"keyword": " "}, {"keyword": "x" * 121}, {"keyword": "x", "year": "202"},
                     {"keyword": "x", "resolution": "8k"}, {"keyword": "a\nb"}]:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                SEARCH.SearchRequest(**data)

    def test_base_url_and_share_canonicalization(self):
        self.assertEqual("http://localhost:8888/pansou", SEARCH.normalize_base(" http://localhost:8888/pansou/ "))
        for url in ["file:///tmp", "https://u:p@host", "https://host?token=secret", "https://host/#x", "https://host:bad"]:
            with self.subTest(url=url), self.assertRaises(SEARCH.SearchError):
                SEARCH.normalize_base(url)
        code, url, password = SEARCH.normalize_share("https://anxia.com/s/example?pwd=abcd&utm_source=test")
        self.assertEqual(("example", "https://115cdn.com/s/example?password=abcd", "abcd"), (code, url, password))


class PluginTests(unittest.TestCase):
    """验证鉴权声明、SDK调用和失败边界。"""

    def setUp(self):
        self.plugin = MODULE.MppgdonTest()
        self.plugin.init_plugin({"enabled": True, "pansou_token": "Bearer private-test-token"})
        self.response = MagicMock(status_code=200)
        self.response.iter_content.return_value = [json.dumps(fixture()).encode()]
        self.client = MagicMock()
        self.client.post_res.return_value = self.response
        self.network = patch.object(MODULE, "RequestUtils", return_value=self.client)
        self.constructor = self.network.start()
        self.addCleanup(self.network.stop)

    def search(self):
        return asyncio.run(self.plugin.search(SEARCH.SearchRequest(keyword="测试剧")))

    def test_sdk_contract_and_redacted_status(self):
        result = self.search()
        self.assertTrue(result.success)
        self.constructor.assert_called_once()
        self.assertTrue(self.constructor.call_args.kwargs["verify"])
        self.assertEqual("Bearer private-test-token", self.constructor.call_args.kwargs["headers"]["Authorization"])
        args, kwargs = self.client.post_res.call_args
        self.assertEqual("https://pansou.tiandechi.com/api/search", args[0])
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(["115"], kwargs["json"]["cloud_types"])
        self.response.close.assert_called_once()
        self.client.close.assert_called_once()
        self.assertNotIn("private-test-token", self.plugin.get_status().model_dump_json())
        self.assertEqual({"success", "message", "data"}, set(result.model_dump()))

    def test_disabled_and_bad_config_do_not_call_network(self):
        for config in [{"enabled": False}, {"enabled": True, "pansou_url": "file:///tmp"},
                       {"enabled": True, "pansou_token": "bad\r\nvalue"}]:
            self.plugin.init_plugin(config)
            self.assertFalse(self.search().success)
        self.client.post_res.assert_not_called()

    def test_http_failures_and_no_retry(self):
        for status in [302, 401, 403, 429, 500, 502]:
            self.response.status_code = status
            self.client.post_res.reset_mock()
            result = self.search()
            self.assertFalse(result.success)
            self.client.post_res.assert_called_once()
            self.assertNotIn("private-test-token", result.model_dump_json())

    def test_network_failure_and_invalid_json(self):
        self.client.post_res.return_value = None
        self.assertFalse(self.search().success)
        self.client.post_res.return_value = self.response
        self.response.iter_content.return_value = [b'<html>not json</html>']
        self.assertFalse(self.search().success)
        self.response.iter_content.side_effect = TimeoutError("must-not-leak")
        self.assertNotIn("must-not-leak", self.search().model_dump_json())

    def test_oversize_and_invalid_utf8(self):
        self.response.iter_content.return_value = [b'x' * (8 * 1024 * 1024 + 1)]
        self.assertFalse(self.search().success)
        self.response.iter_content.return_value = [b'{"results":[],"description":"\xff"}']
        self.assertTrue(self.search().success)

    def test_busy_and_reinitialization(self):
        self.plugin._search_lock.acquire()
        try:
            self.assertFalse(self.search().success)
            self.plugin.init_plugin({"enabled": True})
            self.assertFalse(self.search().success)
            self.client.post_res.assert_not_called()
        finally:
            self.plugin._search_lock.release()
        self.plugin.stop_service()
        self.plugin.stop_service()
        self.assertFalse(self.plugin.get_state())

    def test_metadata_routes_and_federation(self):
        meta = json.loads((ROOT / 'package.v3.json').read_text(encoding='utf-8'))['MppgdonTest']
        self.assertEqual(meta['version'], self.plugin.plugin_version)
        self.assertEqual(meta['name'], self.plugin.plugin_name)
        self.assertEqual('v' + meta['version'], next(iter(meta['history'])))
        self.assertTrue(meta['release'])
        self.assertEqual(('vue', 'dist/assets'), self.plugin.get_render_mode())
        [nav] = self.plugin.get_sidebar_nav()
        self.assertEqual(('main', 'discovery', 'search'), (nav['nav_key'], nav['section'], nav['permission']))
        for route in self.plugin.get_api():
            self.assertEqual('bear', route['auth'])
            self.assertIn('data', route['response_model'].model_fields)

    def test_cancellation_does_not_release_running_search(self):
        started, release = threading.Event(), threading.Event()

        def blocking(*args):
            """模拟仍在进行的只读请求，取消页面等待不应清除它的锁。"""
            started.set()
            release.wait(2)
            return SEARCH.normalize_results(fixture(), SEARCH.SearchRequest(keyword='测试剧'))

        async def scenario():
            task = asyncio.create_task(self.plugin.search(SEARCH.SearchRequest(keyword='测试剧')))
            await asyncio.to_thread(started.wait, 1)
            self.assertTrue(started.is_set())
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            try:
                busy = await self.plugin.search(SEARCH.SearchRequest(keyword='测试剧'))
                self.assertFalse(busy.success)
            finally:
                release.set()

        with patch.object(self.plugin, '_search_sync', side_effect=blocking):
            asyncio.run(scenario())


class ShareSyncTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.settings = {"cms_url": "https://CMS.example:443/", "cms_login_token": "Bearer fake-login-token",
                         "cms_sync_path": "/media/测试影视", "cms_sync_cid": "000", "cms_sync_live": True}

    def prepare(self, **overrides):
        sync = SYNC.ShareSync(SYNC.SyncConfig.from_settings(dict(self.settings, **overrides)), lambda: self.directory)
        items = SEARCH.normalize_results(fixture(), SEARCH.SearchRequest(keyword="测试剧")).items
        data = SEARCH.SearchData(keyword="测试剧", items=items, raw_115=3, duplicates=0, filtered=0)
        data.items[1].password_conflict = True
        sync.add_tickets(data)
        self.assertIsNone(data.items[1].sync_ticket)
        return sync, data.items[0]

    def test_share_sync_dry_run_and_invalid_config(self):
        with self.assertRaises(SEARCH.SearchError):
            SYNC.SyncConfig.from_settings(dict(self.settings, cms_sync_path="/media/../etc"))
        with self.assertRaises(ValidationError):
            SYNC.SyncRequest(ticket="x" * 32, local_path="/media/other")
        sync, item = self.prepare(cms_sync_live=False)
        with patch.object(SYNC, "_request") as request:
            self.assertEqual("not_sent", sync.submit("x" * 32)[0].status)
            self.assertEqual("dry_run", sync.submit(item.sync_ticket)[0].status)
            request.assert_not_called()
        self.assertEqual([], list(self.directory.iterdir()))

    def test_share_sync_payload_and_durable_unknown(self):
        sync, item = self.prepare()
        with patch.object(SYNC, "_request", side_effect=[(200, {"code": 200, "data": {}}), (0, {})]) as request:
            self.assertEqual("unknown", sync.submit(item.sync_ticket)[0].status)
            self.assertEqual("/api/config/share_115_sync", request.call_args_list[0].args[1])
            self.assertEqual("/api/sync/share115", request.call_args.args[1])
            self.assertEqual({"share_code": item.id, "receive_code": item.password, "cid": "0", "local_path": "/media/测试影视"},
                             request.call_args.kwargs["body"])
            self.assertEqual("fake-login-token", request.call_args.args[0].token)
        restarted, item = self.prepare()
        with patch.object(SYNC, "_request") as request:
            self.assertEqual("unknown", restarted.submit(item.sync_ticket)[0].status)
            request.assert_not_called()
        journal = (self.directory / "cms-share-sync.sqlite3").read_bytes()
        for value in (b"fake-login-token", item.id.encode(), b"/media/"):
            self.assertNotIn(value, journal)

    def test_share_sync_preflight_rejection_and_accepted_idempotency(self):
        sync, item = self.prepare()
        with patch.object(SYNC, "_request", return_value=(401, {})) as request:
            self.assertEqual("not_sent", sync.submit(item.sync_ticket)[0].status)
            self.assertEqual(1, request.call_count)
        preflight = (200, {"code": "200", "data": {}})
        with patch.object(SYNC, "_request", side_effect=[preflight, (400, {}), preflight, (200, {"code": 200})]) as request:
            self.assertEqual("rejected", sync.submit(item.sync_ticket)[0].status)
            self.assertEqual("accepted", sync.submit(item.sync_ticket)[0].status)
            self.assertEqual("accepted", sync.submit(item.sync_ticket)[0].status)
            self.assertEqual(4, request.call_count)


if __name__ == '__main__':
    unittest.main()
