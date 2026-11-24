"""PanSou 输入、响应与 115 分享规范化；不读取宿主状态。"""

import re
import unicodedata
from typing import Literal
from urllib.parse import parse_qs, urlencode, urlsplit

from pydantic import BaseModel, Field, field_validator

DEFAULT_URL = "https://pansou.tiandechi.com"
SHARE_HOSTS = {"115.com", "www.115.com", "115cdn.com", "www.115cdn.com", "anxia.com", "www.anxia.com"}
MAX_DUPLICATES_PER_SHARE = 30


class SearchError(Exception):
    """允许展示给用户的受控错误，不携带原始响应或凭据。"""


class SearchRequest(BaseModel):
    """页面只提交搜索参数，不能指定上游地址或认证。"""

    keyword: str = Field(min_length=1, max_length=120)
    year: str = Field(default="", pattern=r"^(?:(?:19|20)\d{2})?$")
    resolution: Literal["all", "2160p", "1080p"] = "all"
    qualities: list[Literal['original', '2160p', '1440p', '1080p', '720p', 'preview']] | None = Field(default=None, min_length=1, max_length=6)
    media_type: Literal["", "movie", "tv"] = ""
    tmdb_id: int | None = Field(default=None, ge=1)
    season: int | None = Field(default=None, ge=0, le=999)

    @field_validator("keyword")
    @classmethod
    def trim_keyword(cls, value: str) -> str:
        """拒绝空白及控制字符关键词。"""
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("请输入有效的影视名称")
        return value


class DuplicateRecord(BaseModel):
    """同一分享的另一条命中记录，只保留供比对的元数据。"""

    title: str
    source: str
    published: str
    quality: str
    origin: Literal["grouped", "raw"]


class SyncTarget(BaseModel):
    mp_path: str
    cms_path: str
    kind: Literal['movie', 'tv']
    season: int | None = None
    reason: str


class SearchItem(BaseModel):
    """校验后的分享卡片，标题标签不代表已核实文件内容。"""

    id: str
    title: str
    url: str
    password: str = ""
    source: str = "PanSou"
    published: str = ""
    quality: str = "未知"
    episode: str = "季集未标注"
    collection: bool = False
    password_conflict: bool = False
    duplicate_records: list[DuplicateRecord] = Field(default_factory=list)
    sync_ticket: str | None = None
    sync_target: SyncTarget | None = None
    sync_error: str = ''


class SearchData(BaseModel):
    """搜索结果与明确的过滤统计。"""

    keyword: str
    items: list[SearchItem]
    raw_115: int
    duplicates: int
    filtered: int
    truncated: bool = False


class StatusData(BaseModel):
    """不含凭据的运行状态。"""

    enabled: bool
    version: str
    pansou_url: str
    token_set: bool
    config_error: str = ""
    sync_mode: Literal["unavailable", "dry_run", "live"] = "unavailable"
    sync_error: str = ""


def normalize_base(value: str) -> str:
    """允许管理员配置自建服务及反向代理子路径。"""
    try:
        value = str(value).strip().rstrip("/")
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        raise SearchError("PanSou 地址格式错误。") from None
    if (parts.scheme not in {"http", "https"} or not parts.hostname
            or parts.username or parts.password or parts.query or parts.fragment
            or any(c.isspace() or ord(c) < 32 for c in value)
            or (port is not None and not 1 <= port <= 65535)):
        raise SearchError("请填写不含账号、查询参数的 PanSou HTTP/HTTPS 服务地址。")
    return value


def normalize_share(url: str, password: str = "") -> tuple[str, str, str]:
    """仅接受115官方分享域名与合法分享码，移除跟踪参数。"""
    try:
        parts = urlsplit(str(url))
        port = parts.port
    except ValueError:
        raise SearchError("分享链接无效。") from None
    match = re.fullmatch(r"/s/([A-Za-z0-9]+)/*", parts.path)
    if (parts.scheme not in {"http", "https"} or parts.hostname not in SHARE_HOSTS
            or parts.username or parts.password or port not in (None, 80, 443) or not match):
        raise SearchError("分享链接无效。")
    query = parse_qs(parts.query)
    password = str(password or next((query[k][0] for k in ("password", "pwd", "receive_code") if query.get(k)), ""))
    if password and not re.fullmatch(r"[A-Za-z0-9]{1,32}", password):
        raise SearchError("分享提取码无效。")
    code = match.group(1)
    url = "https://115cdn.com/s/" + code
    return code, url + ("?" + urlencode({"password": password}) if password else ""), password


def compact(value: str) -> str:
    """统一全半角和大小写，用于关键词匹配。"""
    return "".join(c for c in unicodedata.normalize("NFKC", str(value)).casefold() if c.isalnum())


def classify_quality(title: str) -> tuple[str, str]:
    text = re.sub(r'无广告|去广告|无水印|去水印', '', title)
    if re.search(r'抢先|枪版|含广告|广告|(?<![A-Z0-9])(?:HDCAM|HDTS|HDTC|CAM|TS|TC)(?![A-Z0-9])', text, re.I):
        return 'preview', '抢先版 / 含广告'
    if re.search(r'原盘|BDMV|BDISO|(?<![A-Z0-9])ISO(?![A-Z0-9])|COMPLETE[ ._-]*(?:UHD[ ._-]*)?BLU[ ._-]?RAY', title, re.I):
        return 'original', '原盘'
    if re.search(r'2160|(?<![A-Z0-9])4K(?![A-Z0-9])|\bUHD\b', title, re.I):
        return '2160p', '2160p'
    if re.search(r'1440|(?<![A-Z0-9])2K(?![A-Z0-9])', title, re.I):
        return '1440p', '2K / 1440p'
    if re.search(r'1080', title, re.I):
        return '1080p', '1080p'
    if re.search(r'720', title, re.I):
        return '720p', '720p'
    return 'unknown', '未知'


def normalize_results(payload: dict, request: SearchRequest) -> SearchData:
    """合并原始与分组结果，按分享标识去重并检测提取码冲突。"""
    if not isinstance(payload, dict) or ("code" in payload and str(payload["code"]) not in {"0", "200"}):
        raise SearchError("PanSou 返回业务错误或不兼容的数据。")
    data = payload.get("data", payload)
    if not isinstance(data, dict) or not any(k in data for k in ("results", "merged_by_type")):
        raise SearchError("PanSou 响应缺少搜索结果字段。")
    merged, results = data.get("merged_by_type", {}), data.get("results", [])
    if not isinstance(merged, dict) or not isinstance(results, list) or not isinstance(merged.get("115", []), list):
        raise SearchError("PanSou 搜索结果结构不兼容。")
    raw = [dict(item, title=item.get("note") or item.get("title", ""), origin="grouped")
           for item in merged.get("115", []) if isinstance(item, dict)]
    for result in results:
        if not isinstance(result, dict) or not isinstance(result.get("links", []), list):
            continue
        for link in result.get("links", []):
            if isinstance(link, dict) and link.get("type", link.get("disk_type")) == "115":
                raw.append(dict(link, title=link.get("work_title") or result.get("title", ""),
                                source=result.get("channel") or result.get("unique_id", "PanSou"),
                                datetime=result.get("datetime", ""), origin="raw"))
    items: dict[str, SearchItem] = {}
    duplicates = filtered = 0
    needle = compact(request.keyword)
    if not needle:
        raise SearchError("请输入包含文字或数字的影视名称。")
    for item in raw:
        title = str(item.get("title", "")).strip()[:600]
        years = set(re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", title))
        if (needle not in compact(title) or (request.year and years and request.year not in years)
                or re.search(r"预告|花絮|样片", title, re.I)):
            filtered += 1
            continue
        try:
            code, url, password = normalize_share(item.get("url", ""), item.get("password", ""))
        except SearchError:
            filtered += 1
            continue
        quality_group, quality = classify_quality(title)
        if ((request.qualities is not None and quality_group not in request.qualities)
                or request.qualities is None and request.resolution != 'all' and quality_group != request.resolution):
            filtered += 1
            continue
        source = str(item.get("source", "PanSou"))[:120]
        published = str(item.get("datetime", ""))[:40]
        if code in items:
            duplicates += 1
            current = items[code]
            if len(current.duplicate_records) < MAX_DUPLICATES_PER_SHARE:
                current.duplicate_records.append(DuplicateRecord(
                    title=title, source=source, published=published, quality=quality, origin=item["origin"],
                ))
            if password and current.password and current.password != password:
                current.password_conflict = True
            elif password and not current.password:
                current.password, current.url = password, url
            continue
        episode = re.search(r"S\d{1,2}E\d{1,3}(?:\s*[-~～]\s*(?:S\d{1,2})?E?\d{1,3})?|第\s*\d+\s*(?:[-~～]\s*\d+\s*)?集", title, re.I)
        items[code] = SearchItem(
            id=code, title=title, url=url, password=password,
            source=source, published=published, quality=quality,
            episode=episode.group(0).upper() if episode else "季集未标注",
            collection=bool(re.search(r"合集|全集|全\s*\d+\s*集|\d+\s*[-~～]\s*\d+", title)),
        )
    ordered = sorted(items.values(), key=lambda item: (item.collection, item.episode, item.title))
    return SearchData(keyword=request.keyword, items=ordered[:200], raw_115=len(raw),
                      duplicates=duplicates, filtered=filtered, truncated=len(ordered) > 200)
