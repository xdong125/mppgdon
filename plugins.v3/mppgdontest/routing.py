"""Resolve a CMS target from media identity and the MP filesystem index."""
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
import re
import unicodedata

from .library import LibraryConfig, LibraryIndex
from .search import SearchError, SearchRequest, SyncTarget, compact


def _name_parts(name):
    name = re.sub(r'(?i)[\[{]tmdb(?:id)?[-= ]*\d+[\]}]', '', name).strip()
    years = re.findall(r'(?<!\d)((?:19|20)\d{2})(?!\d)', name)
    title = re.sub(r'[（(](?:19|20)\d{2}[）)]', '', name).strip()
    return compact(title), set(years)


def _component(title):
    title = unicodedata.normalize('NFKC', title)
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip(' .')[:180].rstrip(' .')
    if not compact(title):
        raise SearchError('片名无法生成目录，请调整影视名称。')
    return title


@dataclass
class Work:
    path: Path
    root: Path
    kind: str
    titles: set[str] = field(default_factory=set)
    years: set[str] = field(default_factory=set)
    ids: set[str] = field(default_factory=set)


class TargetResolver:
    def __init__(self, config: LibraryConfig, index: LibraryIndex):
        self.config, self.index = config, index

    def work(self, request: SearchRequest) -> Work:
        entries = self.index.routing_entries(self.config)
        works = {}
        for entry in entries:
            path, root = Path(entry.path), Path(entry.root)
            base = path if entry.entry_type == 'directory' else path.parent
            if entry.kind == 'tv' and re.fullmatch(r'(?i)(?:S|Season[ ._-]*)(\d{1,3})', base.name):
                base = base.parent
            if base == root or not base.is_relative_to(root):
                continue
            key = (entry.kind, str(base))
            work = works.setdefault(key, Work(base, root, entry.kind))
            name, years = _name_parts(base.name)
            work.titles.add(name)
            work.years.update(years)
            is_identity = entry.kind == 'movie' and entry.entry_type == 'media' or (
                entry.kind == 'tv' and entry.entry_type == 'directory' and entry.nfo_path.lower().endswith('tvshow.nfo'))
            if is_identity and entry.scraped:
                work.titles.add(compact(entry.title))
                if entry.year:
                    work.years.add(entry.year)
                if entry.tmdb_id:
                    work.ids.add(entry.tmdb_id)

        choices, exact = [], []
        title = compact(request.keyword)
        for work in works.values():
            if request.media_type and request.media_type != work.kind:
                continue
            if not work.path.is_dir():
                continue
            if request.tmdb_id and str(request.tmdb_id) in work.ids:
                exact.append(work)
                continue
            if request.tmdb_id and work.ids:
                continue
            if title in work.titles and (not request.year or not work.years or request.year in work.years):
                choices.append(work)
        choices = exact or choices
        if len(choices) > 1:
            raise SearchError('媒体库匹配到多个目录，请核对影片类型和年份，避免放错位置。')
        if choices:
            return choices[0]
        if not request.media_type:
            raise SearchError('无法唯一识别电影或电视剧，请选择类型后重新搜索。')
        roots = dict(self.config.roots)
        if request.media_type not in roots:
            raise SearchError('请先保存对应的电影或电视剧根目录。')
        if request.media_type == 'movie' and not request.year:
            raise SearchError('新建电影目录需要年份，请填写年份后重新搜索。')
        root = Path(roots[request.media_type])
        name = _component(request.keyword)
        if request.media_type == 'movie':
            name += f' ({request.year})'
        proposed = root / name
        conflict = works.get((request.media_type, str(proposed)))
        if conflict and (request.tmdb_id and conflict.ids or request.year and conflict.years):
            raise SearchError('预期目录已有其他影视身份，请先核对媒体库，未自动覆盖。')
        return Work(proposed, root, request.media_type)

    def plan(self, request, titles, work: Work | None = None) -> SyncTarget:
        work = work or self.work(request)
        season = None
        path = work.path
        if work.kind == 'tv':
            seasons = set()
            for title in titles:
                for start, end in re.findall(r'(?i)(?<![A-Z0-9])S(\d{1,3})(?:\s*[-~～]\s*S?(\d{1,3}))?', title):
                    seasons.add(int(start))
                    if end:
                        seasons.add(int(end))
                for value in re.findall(r'第\s*(\d{1,3}|[一二三四五六七八九十]+)\s*季', title):
                    if value.isdigit():
                        seasons.add(int(value))
                    elif value in ('一', '二', '三', '四', '五', '六', '七', '八', '九', '十'):
                        seasons.add(('一', '二', '三', '四', '五', '六', '七', '八', '九', '十').index(value) + 1)
                    else:
                        raise SearchError('季号不明确，请填写季号后重新搜索。')
                if re.search(r'(?:\d+|[一二三四五六七八九十]+)\s*[-~～至]\s*(?:\d+|[一二三四五六七八九十]+)\s*季|全\s*(?:[2-9]|\d{2,})\s*季', title):
                    raise SearchError('该分享包含多季，不能整包同步到单一季目录，请先选单季分享。')
            if len(seasons) > 1:
                raise SearchError('该分享季号冲突或包含多季，请先选单季分享。')
            season = next(iter(seasons)) if seasons else request.season
            if season is None:
                raise SearchError('未识别季号，请在搜索栏填写季号后重新搜索。')
            if seasons and request.season is not None and request.season != season:
                raise SearchError('填写的季号与分享标题不符，请核对后重新搜索。')
            aliases = [child for child in work.path.iterdir() if child.is_dir()
                       and re.fullmatch(rf'(?i)(?:S|Season[ ._-]*)0*{season}', child.name)] if work.path.is_dir() else []
            if len(aliases) > 1:
                raise SearchError('同一季匹配到多个目录，请先核对已有季目录。')
            path = aliases[0] if aliases else work.path / f'S{season:02d}'
        mp_path = str(path)
        cms_path = self.config.cms_path(mp_path)
        cms = PurePosixPath(cms_path)
        if (not cms.is_absolute() or '\\' in cms_path or '..' in cms.parts or len(cms_path) > 512
                or any(ord(ch) < 32 for ch in cms_path)):
            raise SearchError('CMS 目标路径无效，请检查 MP→CMS 路径替换。')
        self.ensure_directory(work.root, path, create=False)
        return SyncTarget(mp_path=mp_path, cms_path=cms_path, kind=work.kind, season=season,
                          reason='复用已有目录' if path.is_dir() else '将创建目标目录')

    @staticmethod
    def ensure_directory(root: Path, path: Path, *, create: bool):
        if not root.is_dir() or root.is_symlink() or root.resolve() != root.absolute():
            raise SearchError('媒体根目录不可用或包含符号链接，请检查 MP 挂载。')
        if path == root or not path.is_relative_to(root):
            raise SearchError('目标目录必须在对应媒体根目录内。')
        current = root
        for component in path.relative_to(root).parts:
            current = current / component
            if current.is_symlink() or current.exists() and not current.is_dir():
                raise SearchError('目标目录存在文件或符号链接冲突，未提交。')
            if create:
                current.mkdir(exist_ok=True)
                if current.is_symlink() or not current.is_dir():
                    raise SearchError('目标目录状态发生变化，未提交。')
