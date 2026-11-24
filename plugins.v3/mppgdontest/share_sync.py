"""Single-click CMS share sync with a durable, credential-free dispatch guard."""

from collections import OrderedDict
from contextlib import closing
from dataclasses import dataclass, field
import hashlib
from http.client import HTTPException
import json
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from typing import Callable, Literal
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from pydantic import BaseModel, ConfigDict, Field

from .search import SearchData, SearchError, SearchRequest, SyncTarget
from .routing import TargetResolver

_SYNC_LOCK = threading.Lock()
_REJECTED = {400, 401, 403, 404, 405, 422, 429}
_TICKET_TTL = 3600
_MAX_TICKETS = 1200


class SyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket: str = Field(pattern=r"^[A-Za-z0-9_-]{32}$")


class SyncResult(BaseModel):
    status: Literal["dry_run", "accepted", "unknown", "rejected", "not_sent"]


@dataclass(frozen=True)
class SyncConfig:
    base: str
    token: str = field(repr=False)
    cid: str
    live: bool

    @classmethod
    def from_settings(cls, values: dict) -> "SyncConfig | None":
        raw_base = str(values.get("cms_url") or "").strip()
        live = values.get("cms_sync_live") is True
        if not raw_base and not live:
            return None
        try:
            parts = urlsplit(raw_base)
            port = parts.port
        except ValueError:
            raise SearchError("CMS 地址格式无效。") from None
        if (parts.scheme not in ("http", "https") or not parts.hostname or port == 0
                or parts.username is not None or parts.password is not None or parts.path not in ("", "/")
                or "?" in raw_base or "#" in raw_base or "\\" in raw_base
                or any(ch.isspace() or ord(ch) < 32 for ch in raw_base)):
            raise SearchError("CMS 地址须为 http(s)://主机:端口，不带路径、账号或查询参数。")
        host = parts.hostname.lower()
        if ":" in host:
            host = f"[{host}]"
        if port and port != {"http": 80, "https": 443}[parts.scheme]:
            host += f":{port}"
        raw_token = str(values.get("cms_login_token") or "").strip()
        token = re.sub(r"^(?:Authorization:\s*)?Bearer\s+", "", raw_token, flags=re.I).strip()
        if (raw_token or live) and not re.fullmatch(r"[A-Za-z0-9._~+/=-]{1,8192}", token):
            raise SearchError("请填写 CMS 网页登录 Bearer Token，不要填写 Cookie。")
        cid = str(values.get("cms_sync_cid", "0")).strip()
        if not re.fullmatch(r"[0-9]{1,20}", cid):
            raise SearchError("分享目录 CID 必须是数字，0 表示整个分享。")
        return cls(f"{parts.scheme}://{host}", token, str(int(cid)), live)


@dataclass(frozen=True)
class Candidate:
    share_code: str
    receive_code: str = field(repr=False)
    expires: float
    context: SearchRequest
    titles: tuple[str, ...]
    target: SyncTarget


class ShareSync:
    def __init__(self, config: SyncConfig, data_path: Callable[[], Path], resolver: TargetResolver):
        self.config = config
        self._data_path = data_path
        self._tickets: OrderedDict[str, Candidate] = OrderedDict()
        self._ticket_lock = threading.Lock()
        self.resolver = resolver

    def add_tickets(self, result: SearchData, context: SearchRequest) -> None:
        now = time.monotonic()
        try:
            work = self.resolver.work(context)
        except (SearchError, OSError, sqlite3.Error) as error:
            message = str(error) if isinstance(error, SearchError) else '无法匹配媒体目录，请检查挂载及索引。'
            for item in result.items:
                item.sync_error = message
            return
        with self._ticket_lock:
            while self._tickets and next(iter(self._tickets.values())).expires <= now:
                self._tickets.popitem(last=False)
            for item in result.items:
                if item.password_conflict:
                    continue
                titles = tuple([item.title, *(row.title for row in item.duplicate_records)])
                try:
                    target = self.resolver.plan(context, titles, work)
                except (SearchError, OSError) as error:
                    item.sync_error = str(error) if isinstance(error, SearchError) else '目标目录不可用，请检查 MP 挂载。'
                    continue
                ticket = secrets.token_urlsafe(24)
                self._tickets[ticket] = Candidate(item.id, item.password, now + _TICKET_TTL, context.model_copy(deep=True), titles, target)
                item.sync_ticket = ticket
                item.sync_target = target
            while len(self._tickets) > _MAX_TICKETS:
                self._tickets.popitem(last=False)

    def submit(self, ticket: str) -> tuple[SyncResult, str]:
        with self._ticket_lock:
            candidate = self._tickets.get(ticket)
        if candidate is None or candidate.expires <= time.monotonic():
            return _result("not_sent", "搜索记录已过期或设置已更新，请重新搜索后提交。")
        if not _SYNC_LOCK.acquire(blocking=False):
            return _result("not_sent", "已有分享同步正在提交，请稍后手动点击。")
        try:
            try:
                current = self.resolver.plan(candidate.context, candidate.titles)
                if (current.mp_path, current.cms_path) != (candidate.target.mp_path, candidate.target.cms_path):
                    return _result('not_sent', '目标目录匹配已变化，请重新搜索核对后提交。')
            except (SearchError, OSError, sqlite3.Error):
                return _result('not_sent', '目标目录无法复核，请检查挂载和索引后重新搜索。')
            if not self.config.live:
                return _result("dry_run", f"演练目标：{current.cms_path}；未创建目录或请求 CMS。")
            return self._submit_live(candidate)
        finally:
            _SYNC_LOCK.release()

    def _submit_live(self, candidate: Candidate) -> tuple[SyncResult, str]:
        config = self.config
        key = hashlib.sha256(json.dumps([config.base, candidate.target.cms_path, config.cid, candidate.share_code]).encode()).hexdigest()
        try:
            db_path = self._data_path() / "cms-share-sync.sqlite3"
            with closing(sqlite3.connect(db_path, timeout=3)) as db:
                return self._dispatch(db, key, candidate)
        except (sqlite3.Error, OSError):
            return _result("not_sent", "无法打开同步记录，未提交。请检查 MoviePilot 插件数据目录。")

    def _dispatch(self, db: sqlite3.Connection, key: str, candidate: Candidate) -> tuple[SyncResult, str]:
        db.execute("CREATE TABLE IF NOT EXISTS dispatch (key TEXT PRIMARY KEY, state TEXT NOT NULL)")
        previous = db.execute("SELECT state FROM dispatch WHERE key = ?", (key,)).fetchone()
        if previous:
            if previous[0] == "accepted":
                return _result("accepted", "此分享已向该目录提交，未重复发送。请在 CMS 核对 STRM。")
            return _result("unknown", "此分享已有待核实记录，未重复发送。请在 CMS 核对。")

        config = self.config
        status, response = _request(config, "/api/config/share_115_sync", timeout=12)
        if not 200 <= status < 300 or _code(response) != 200 or not isinstance(response.get("data"), dict):
            return _result("not_sent", "CMS 只读验证未通过，未提交同步。请检查 CMS 地址、网页登录 Token 和版本。")

        try:
            work = self.resolver.work(candidate.context)
            self.resolver.ensure_directory(work.root, Path(candidate.target.mp_path), create=True)
        except (SearchError, OSError, sqlite3.Error):
            return _result('not_sent', '无法创建或访问 MP 目标目录，请检查挂载和写权限；未请求 CMS 同步。')

        inserted = db.execute("INSERT OR IGNORE INTO dispatch VALUES (?, 'pending')", (key,)).rowcount
        db.commit()
        if not inserted:
            return _result("unknown", "该分享已有提交记录，未重复发送。请在 CMS 核对。")

        status, response = _request(config, "/api/sync/share115", timeout=25, body={
            "share_code": candidate.share_code, "receive_code": candidate.receive_code,
            "cid": config.cid, "local_path": candidate.target.cms_path,
        })
        code = _code(response)
        try:
            if 200 <= status < 300 and code == 200:
                db.execute("UPDATE dispatch SET state = 'accepted' WHERE key = ?", (key,))
                db.commit()
                return _result("accepted", "CMS 已受理；请在 CMS 和目标目录核实 STRM 是否生成。")
            rejection = status if status in _REJECTED else code if 200 <= status < 300 and code in _REJECTED else None
            if rejection:
                db.execute("DELETE FROM dispatch WHERE key = ?", (key,))
                db.commit()
                return _result("rejected", f"CMS 明确拒绝了请求（{rejection}），未自动重试。")
        except sqlite3.Error:
            pass  # The prior committed reservation still blocks a second submit.
        return _result("unknown", "CMS 受理结果不确定，请到 CMS 核对；不会重复发送。")


def _result(status, message: str) -> tuple[SyncResult, str]:
    return SyncResult(status=status), message


def _code(response: dict) -> int | None:
    value = response.get("code")
    if type(value) is int or isinstance(value, str) and re.fullmatch(r"[0-9]{1,3}", value.strip()):
        return int(value)
    return None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request(config: SyncConfig, route: str, *, timeout: int, body: dict | None = None, bearer: bool = True) -> tuple[int, dict]:
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if bearer:
        headers['Authorization'] = f'Bearer {config.token}'
    request = Request(config.base + route, data=json.dumps(body).encode() if body is not None else None,
                      headers=headers)
    try:
        with opener.open(request, timeout=timeout) as response:
            content = response.read(256 * 1024 + 1)
            if len(content) > 256 * 1024:
                return response.status, {}
            data = json.loads(content)
            return response.status, data if isinstance(data, dict) else {}
    except HTTPError as error:
        error.close()
        return error.code, {}
    except (OSError, ValueError, HTTPException, RecursionError):
        return 0, {}
