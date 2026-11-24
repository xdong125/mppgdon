"""User-triggered CMS official OPEN API transfers; no media directory operations."""
from collections import OrderedDict
from contextlib import closing
from dataclasses import dataclass, field
import hashlib
import secrets
import sqlite3
import threading
import time

from pydantic import BaseModel, ConfigDict, Field

from .search import SearchData, SearchError
from .share_sync import SyncConfig, SyncResult, _code, _request, _REJECTED, _SYNC_LOCK


class TransferRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ticket: str = Field(pattern=r'^[A-Za-z0-9_-]{32}$')
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{16,80}$')
    expected_attempt: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_-]{16,80}$')


class TransferResult(SyncResult):
    attempt_id: str | None = None
    retryable: bool = False


@dataclass(frozen=True)
class TransferConfig:
    base: str
    token: str = field(repr=False)
    live: bool

    @classmethod
    def from_settings(cls, values):
        token = str(values.get('cms_api_token') or '').strip()
        live = values.get('cms_transfer_live') is True
        if not values.get('cms_url') and not token and not live:
            return None
        # Reuse root URL validation without relying on a CMS web login.
        connection = SyncConfig.from_settings({'cms_url': values.get('cms_url', '')})
        if connection is None:
            raise SearchError('请先保存 CMS 根地址。')
        if live and not token:
            raise SearchError('请填写 CMS_API_TOKEN 后再开启真实转存。')
        if len(token) > 8192 or any(ord(char) < 32 or ord(char) > 126 for char in token):
            raise SearchError('CMS_API_TOKEN 格式错误，请重新填写。')
        return cls(connection.base, token, live)


@dataclass(frozen=True)
class TransferCandidate:
    code: str
    url: str = field(repr=False)
    expires: float


def _result(status, message, attempt_id=None):
    return TransferResult(status=status, attempt_id=attempt_id, retryable=status == 'rejected'), message


class TransferManager:
    def __init__(self, config: TransferConfig, data_path):
        self.config, self._data_path = config, data_path
        self._lock = threading.Lock()
        self._tickets: OrderedDict[str, TransferCandidate] = OrderedDict()

    def add_tickets(self, result: SearchData):
        now = time.monotonic()
        with self._lock:
            while self._tickets and next(iter(self._tickets.values())).expires <= now:
                self._tickets.popitem(last=False)
            for item in result.items:
                if item.password_conflict:
                    continue
                ticket = secrets.token_urlsafe(24)
                self._tickets[ticket] = TransferCandidate(item.id, item.url, now + 3600)
                item.transfer_ticket = ticket
            while len(self._tickets) > 1200:
                self._tickets.popitem(last=False)

    def submit(self, payload: TransferRequest):
        with self._lock:
            candidate = self._tickets.get(payload.ticket)
        if candidate is None or candidate.expires <= time.monotonic():
            return _result('not_sent', '资源或配置已更新，请重新搜索后转存。')
        if not self.config.live:
            return _result('dry_run', '转存演练完成，未请求 CMS，也未保存网盘文件。')
        if not _SYNC_LOCK.acquire(blocking=False):
            return _result('not_sent', '已有 CMS 请求正在提交，请稍后手动点击。')
        try:
            key = hashlib.sha256((self.config.base + '\n' + candidate.code).encode()).hexdigest()
            with closing(sqlite3.connect(self._data_path() / 'cms-transfer.sqlite3', timeout=3)) as db:
                return self._dispatch(db, key, candidate, payload)
        except (OSError, sqlite3.Error):
            return _result('not_sent', '无法准备转存记录，未请求 CMS。请检查插件数据目录。')
        finally:
            _SYNC_LOCK.release()

    def _dispatch(self, db, key, candidate, payload):
        db.executescript('''
            CREATE TABLE IF NOT EXISTS jobs (key TEXT PRIMARY KEY, state TEXT NOT NULL, request_id TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS attempts (request_id TEXT PRIMARY KEY, key TEXT NOT NULL, state TEXT NOT NULL);
        ''')
        db.execute('BEGIN IMMEDIATE')
        replay = db.execute('SELECT key,state FROM attempts WHERE request_id=?', (payload.request_id,)).fetchone()
        if replay:
            if replay[0] != key:
                return _result('not_sent', '请求编号已使用，请重新搜索。')
            status = replay[1] if replay[1] in ('accepted', 'rejected') else 'unknown'
            return _result(status, '此操作已有记录，未重复发送；请核对上次转存结果。', payload.request_id)
        previous = db.execute('SELECT state,request_id FROM jobs WHERE key=?', (key,)).fetchone()
        if previous:
            if previous[0] != 'rejected':
                status = 'accepted' if previous[0] == 'accepted' else 'unknown'
                return _result(status, '此分享已转存提交或结果待核实，未重复发送。请在 CMS 核对。', previous[1])
            if payload.expected_attempt != previous[1]:
                return _result('rejected', '上次转存被明确拒绝；确认 CMS 没有任务后，可点击手动重试。', previous[1])
        db.execute('INSERT INTO attempts VALUES (?,?,?)', (payload.request_id, key, 'pending'))
        db.execute('INSERT OR REPLACE INTO jobs VALUES (?,?,?)', (key, 'pending', payload.request_id))
        db.commit()

        status = 'unknown'
        message = '转存受理结果不确定，请在 CMS 核对；不会自动重试。'
        try:
            http_status, response = _request(self.config, '/api/cloud/add_share_down_by_token', timeout=30,
                                             body={'url': candidate.url, 'token': self.config.token}, bearer=False)
            code = _code(response)
            if 200 <= http_status < 300 and code == 200:
                status, message = 'accepted', 'CMS 已受理转存；请到 CMS 和网盘核实是否保存成功。'
            elif http_status in _REJECTED or 200 <= http_status < 300 and code in _REJECTED:
                status, message = 'rejected', f'CMS 明确拒绝转存（{http_status if http_status in _REJECTED else code}）。请核对 CMS_API_TOKEN 和分享链接。'
            db.execute('UPDATE jobs SET state=? WHERE key=?', (status, key))
            db.execute('UPDATE attempts SET state=? WHERE request_id=?', (status, payload.request_id))
            db.commit()
            return _result(status, message, payload.request_id)
        except (OSError, sqlite3.Error):
            # A committed pending reservation blocks replay even if the result cannot be written.
            return _result('unknown', '转存结果未能确认，请在 CMS 核对；不会自动重试。', payload.request_id)
