"""Rebuildable, read-only media filesystem index. Never reads STRM contents."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import threading
import uuid
import xml.etree.ElementTree as ET

from pydantic import BaseModel, Field

from .search import SearchError

MEDIA_EXTENSIONS = {'.strm', '.mkv', '.mp4', '.avi', '.mov', '.ts', '.m2ts', '.wmv', '.iso'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
_SCAN_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


@dataclass(frozen=True)
class LibraryConfig:
    roots: tuple[tuple[str, str], ...]
    mappings: tuple[tuple[str, str], ...]

    @classmethod
    def from_settings(cls, settings: dict):
        roots = []
        for kind, key in [('movie', 'library_movie_root'), ('tv', 'library_tv_root')]:
            value = str(settings.get(key) or '').strip()
            if not value:
                continue
            path = Path(value)
            if not path.is_absolute() or '..' in path.parts or any(ord(c) < 32 for c in value) or path == Path(path.anchor):
                raise SearchError('媒体根目录必须是 MP 可访问的绝对路径，不能是文件系统根目录或包含 ..。')
            roots.append((kind, str(path)))
        if len(roots) == 2:
            a, b = (Path(root).absolute() for _, root in roots)
            if a.is_relative_to(b) or b.is_relative_to(a):
                raise SearchError('电影与电视剧根目录不能相同或互相包含。')
        mappings = []
        for line in str(settings.get('library_path_mapping') or '').splitlines():
            if not line.strip():
                continue
            if line.count('#') != 1:
                raise SearchError('每条路径替换填写为 MP前缀#CMS前缀，一行一条。')
            source, target = (part.strip() for part in line.split('#'))
            if not source or not Path(source).is_absolute() or '..' in Path(source).parts:
                raise SearchError('路径替换的 MP 前缀须为绝对路径。')
            dest = PurePosixPath(target)
            if (not dest.is_absolute() or '..' in dest.parts or '\\' in target
                    or any(ord(c) < 32 for c in line)):
                raise SearchError('CMS 路径须为 Linux 绝对路径，不含 ..。')
            source = str(Path(source))
            if any(source == old for old, _ in mappings):
                raise SearchError('同一 MP 前缀不能设置多个替换目标。')
            mappings.append((source, str(dest)))
        return cls(tuple(roots), tuple(sorted(mappings, key=lambda row: len(Path(row[0]).parts), reverse=True)))

    def cms_path(self, value: str) -> str:
        path = Path(value)
        for source, target in self.mappings:
            try:
                tail = path.relative_to(source)
                return str(PurePosixPath(target).joinpath(*tail.parts))
            except ValueError:
                continue
        return str(path)


class LibraryEntry(BaseModel):
    path: str
    parent: str
    root: str
    kind: str
    entry_type: str
    title: str = ''
    year: str = ''
    tmdb_id: str = ''
    season: str = ''
    episode: str = ''
    size: int = 0
    scraped: bool | None = None
    nfo_state: str = ''
    nfo_path: str = ''
    missing_images: list[str] = Field(default_factory=list)
    cms_path: str = ''
    present: bool = True
    checked_at: str = ''


class ScanState(BaseModel):
    status: str = 'idle'
    started_at: str = ''
    finished_at: str = ''
    entries: int = 0
    parsed_nfo: int = 0
    reused_nfo: int = 0
    skipped_links: int = 0
    errors: list[str] = Field(default_factory=list)


class LibraryView(BaseModel):
    roots: list[dict[str, str]] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    scan: ScanState = Field(default_factory=ScanState)
    items: list[LibraryEntry] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    config_error: str = ''


def _parse_nfo(path: Path) -> dict:
    try:
        with path.open('rb') as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper() or b'\x00' in raw:
            return {'state': 'invalid'}
        node = ET.fromstring(raw)
        if node.tag not in {'movie', 'tvshow', 'episodedetails'} or not (node.findtext('title') or '').strip():
            return {'state': 'invalid'}
        metadata = {'state': 'valid', 'tag': node.tag}
        for key in ('title', 'year', 'season', 'episode'):
            metadata[key] = (node.findtext(key) or '').strip()[:200]
        tmdb = node.find("uniqueid[@type='tmdb']")
        metadata['tmdb_id'] = ((tmdb.text if tmdb is not None else node.findtext('tmdbid')) or '').strip()[:32]
        return metadata
    except (ET.ParseError, ValueError):
        return {'state': 'invalid'}


class LibraryIndex:
    def __init__(self, data_path):
        self._data_path = data_path
        self._init_lock = threading.Lock()
        self._initialized = False
        self._stop = threading.Event()
        self._thread = None

    @contextmanager
    def database(self):
        db = sqlite3.connect(self._data_path() / 'media-library.sqlite3', timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with self._init_lock:
                if db.execute('PRAGMA user_version').fetchone()[0] > 1:
                    raise sqlite3.DatabaseError('Newer library schema')
                db.executescript('''
                    CREATE TABLE IF NOT EXISTS entries (
                        path TEXT PRIMARY KEY, parent TEXT NOT NULL, root TEXT NOT NULL,
                        kind TEXT NOT NULL, entry_type TEXT NOT NULL, size INTEGER NOT NULL,
                        mtime INTEGER NOT NULL, meta TEXT NOT NULL, detail TEXT NOT NULL,
                        generation TEXT NOT NULL, present INTEGER NOT NULL DEFAULT 1);
                    CREATE INDEX IF NOT EXISTS entries_root_parent ON entries(root, parent);
                    CREATE INDEX IF NOT EXISTS entries_kind_type ON entries(kind, entry_type);
                    CREATE TABLE IF NOT EXISTS scan (id INTEGER PRIMARY KEY CHECK(id=1), detail TEXT NOT NULL);
                    PRAGMA user_version=1;
                ''')
                if not self._initialized:
                    row = db.execute('SELECT detail FROM scan WHERE id=1').fetchone()
                    if row:
                        state = ScanState.model_validate_json(row['detail'])
                        if state.status == 'running':
                            state.status = 'interrupted'
                            state.errors = ['上次扫描中断，请手动重新扫描。']
                            self._save_state(db, state)
                    self._initialized = True
            yield db
        finally:
            db.close()

    @staticmethod
    def _save_state(db, state):
        db.execute('INSERT OR REPLACE INTO scan VALUES (1, ?)', (state.model_dump_json(),))
        db.commit()

    def start(self, config: LibraryConfig) -> None:
        if not config.roots:
            raise SearchError('请先在插件设置保存电影或电视剧根目录。')
        if not _SCAN_LOCK.acquire(blocking=False):
            raise SearchError('已有媒体库扫描正在进行，请等待完成。')
        self._stop.clear()
        state = ScanState(status='running', started_at=_now())
        try:
            with self.database() as db:
                self._save_state(db, state)
            self._thread = threading.Thread(target=self._run, args=(config, state), daemon=True, name='mppgdon-library-scan')
            self._thread.start()
        except Exception:
            _SCAN_LOCK.release()
            raise

    def stop(self):
        self._stop.set()

    def _run(self, config, state):
        try:
            with self.database() as db:
                for kind, root in config.roots:
                    if self._stop.is_set():
                        break
                    try:
                        self._scan_root(db, kind, Path(root), state)
                    except OSError:
                        if len(state.errors) < 10:
                            state.errors.append(f'{root} 扫描未完成：检查挂载、权限或文件变化；保留上次索引。')
                        db.rollback()
                state.status = 'interrupted' if self._stop.is_set() else 'partial' if state.errors else 'complete'
                state.finished_at = _now()
                self._save_state(db, state)
        except (OSError, sqlite3.Error):
            # Keep the committed running marker; a later page load/restart can identify interruption.
            self._initialized = False
        finally:
            _SCAN_LOCK.release()

    def _scan_root(self, db, kind, root, state):
        # Configured mounts must exist. No mkdir, link following, STRM reads or media writes.
        if root.is_symlink() or root.resolve() != root.absolute() or not root.is_dir():
            raise OSError('Unavailable media root')
        generation = uuid.uuid4().hex

        def fail(error):
            raise error

        for folder, directories, names in os.walk(root, onerror=fail, followlinks=False):
            if self._stop.is_set():
                return
            path = Path(folder)
            safe_dirs = []
            for name in directories:
                if (path / name).is_symlink():
                    state.skipped_links += 1
                else:
                    safe_dirs.append(name)
            directories[:] = safe_dirs
            cache = {row['path']: row for row in db.execute('SELECT path,size,mtime,meta FROM entries WHERE root=? AND parent=?', (str(root), str(path)))}
            files, metadata = {}, {}
            for name in names:
                file = path / name
                if file.is_symlink():
                    state.skipped_links += 1
                    continue
                if not file.is_file():
                    continue
                stat = file.stat()
                key = name.casefold()
                if key in files:
                    raise OSError('Ambiguous case-insensitive filenames')
                files[key] = (file, stat)
                if file.suffix.lower() == '.nfo':
                    previous = cache.get(str(file))
                    if previous and previous['size'] == stat.st_size and previous['mtime'] == stat.st_mtime_ns:
                        metadata[key] = json.loads(previous['meta'])
                        state.reused_nfo += 1
                    else:
                        metadata[key] = _parse_nfo(file)
                        state.parsed_nfo += 1
                    after = file.stat()
                    if (after.st_size, after.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
                        raise OSError('NFO changed during read')
            checked = _now()
            directory = LibraryEntry(path=str(path), parent=str(path.parent), root=str(root), kind=kind,
                                     entry_type='directory', title=path.name, checked_at=checked)
            if kind == 'tv' and ('tvshow.nfo' in metadata or path.parent == root):
                nfo_path = str(files['tvshow.nfo'][0]) if 'tvshow.nfo' in files else str(path / 'tvshow.nfo')
                self._apply_metadata(directory, metadata.get('tvshow.nfo', {'state': 'missing'}), nfo_path, 'tvshow')
                directory.missing_images = self._missing_images(files, ['poster', 'background', 'logo'])
            self._upsert(db, directory, path.stat(), {}, generation)
            for name, (file, stat) in files.items():
                ext = file.suffix.lower()
                entry_type = 'media' if ext in MEDIA_EXTENSIONS else 'nfo' if ext == '.nfo' else 'image' if ext in IMAGE_EXTENSIONS else 'other'
                entry = LibraryEntry(path=str(file), parent=str(path), root=str(root), kind=kind,
                                     entry_type=entry_type, title=file.name, size=stat.st_size, checked_at=checked)
                if entry_type == 'media':
                    nfo_name = (file.stem + '.nfo').casefold()
                    if kind == 'movie' and nfo_name not in metadata and 'movie.nfo' in metadata:
                        nfo_name = 'movie.nfo'
                    meta = metadata.get(nfo_name, {'state': 'missing'})
                    self._apply_metadata(entry, meta, str(path / nfo_name) if nfo_name not in files else str(files[nfo_name][0]),
                                         'movie' if kind == 'movie' else 'episodedetails')
                    entry.missing_images = self._missing_images(files, ['thumbnail'] if kind == 'tv' else ['poster', 'background'], file.stem)
                    if kind == 'tv' and not entry.season:
                        season = re.search(r'(?i)(?:^|[^a-z])S(\d{1,3})(?:E|[^0-9]|$)', file.stem)
                        if not season:
                            season = re.fullmatch(r'(?i)S(\d{1,3})', path.name)
                        entry.season = str(int(season[1])) if season else ''
                    if kind == 'tv' and not entry.episode:
                        episode = re.search(r'(?i)S\d{1,3}E(\d{1,4})', file.stem)
                        entry.episode = str(int(episode[1])) if episode else ''
                self._upsert(db, entry, stat, metadata.get(name, {}), generation)
                state.entries += 1
            state.entries += 1
            self._save_state(db, state)
        if not self._stop.is_set():
            previous = db.execute('SELECT count(*) FROM entries WHERE root=? AND generation<>? AND present=1', (str(root), generation)).fetchone()[0]
            current = db.execute('SELECT count(*) FROM entries WHERE root=? AND generation=?', (str(root), generation)).fetchone()[0]
            if previous and current == 1:
                raise OSError('Previously indexed root is now empty; verify the mount')
            db.execute('UPDATE entries SET present=0 WHERE root=? AND generation<>?', (str(root), generation))
            db.commit()

    @staticmethod
    def _apply_metadata(entry, meta, nfo_path, expected):
        state = meta.get('state', 'missing')
        if state == 'valid' and meta.get('tag') != expected:
            state = 'invalid'
        entry.nfo_state, entry.nfo_path = state, nfo_path
        entry.scraped = state == 'valid'
        if entry.scraped:
            for field in ('title', 'year', 'tmdb_id', 'season', 'episode'):
                setattr(entry, field, meta.get(field, ''))

    @staticmethod
    def _missing_images(files, roles, stem=''):
        available = {Path(name).stem for name, (_, stat) in files.items()
                     if Path(name).suffix in IMAGE_EXTENSIONS and stat.st_size > 0}
        choices = {'poster': {'poster', stem.casefold(), (stem + '-poster').casefold()},
                   'background': {'fanart', 'backdrop', (stem + '-fanart').casefold()},
                   'logo': {'logo', 'clearlogo'},
                   'thumbnail': {stem.casefold(), (stem + '-thumb').casefold()}}
        return [role for role in roles if not (available & choices[role])]

    @staticmethod
    def _upsert(db, entry, stat, meta, generation):
        # Derived fields are cheap to refresh; only NFO XML parsing uses the stat cache.
        db.execute('''INSERT OR REPLACE INTO entries
            (path,parent,root,kind,entry_type,size,mtime,meta,detail,generation,present)
            VALUES (?,?,?,?,?,?,?,?,?,?,1)''',
            (entry.path, entry.parent, entry.root, entry.kind, entry.entry_type, stat.st_size,
             stat.st_mtime_ns, json.dumps(meta), entry.model_dump_json(), generation))

    def view(self, config, *, page=1, keyword='', kind='', entry_type='media', scrape='', parent='', include_missing=False):
        roots = [root for _, root in config.roots]
        view = LibraryView(roots=[{'kind': kind, 'mp_path': root, 'cms_path': config.cms_path(root)} for kind, root in config.roots], page=page)
        with self.database() as db:
            state = db.execute('SELECT detail FROM scan WHERE id=1').fetchone()
            if state:
                view.scan = ScanState.model_validate_json(state['detail'])
            if not roots:
                return view
            scope = 'root IN (' + ','.join('?' for _ in roots) + ')'
            summary = db.execute(f'''SELECT count(*) AS entries,
                coalesce(sum(entry_type='directory'),0) AS directories,
                coalesce(sum(entry_type='media'),0) AS media,
                coalesce(sum(entry_type='directory' AND json_extract(detail,'$.nfo_path') LIKE '%tvshow.nfo'),0) AS shows,
                coalesce(sum(entry_type='directory' AND json_extract(detail,'$.scraped')=1),0) AS shows_scraped,
                coalesce(sum(entry_type='media' AND lower(path) LIKE '%.strm'),0) AS strm,
                coalesce(sum(entry_type='media' AND json_extract(detail,'$.scraped')=1),0) AS scraped,
                coalesce(sum(entry_type='media' AND json_extract(detail,'$.scraped')=0),0) AS not_scraped,
                coalesce(sum(entry_type='media' AND json_extract(detail,'$.scraped')=1 AND json_array_length(detail,'$.missing_images')>0),0) AS incomplete
                FROM entries WHERE {scope} AND present=1''', roots).fetchone()
            view.summary = dict(summary)
            clauses, args = [scope], list(roots)
            if not include_missing:
                clauses.append('present=1')
            if keyword:
                clauses.append("(instr(lower(path),lower(?))>0 OR instr(lower(json_extract(detail,'$.title')),lower(?))>0)")
                args.extend([keyword, keyword])
            for column, value in [('kind', kind), ('entry_type', entry_type), ('parent', parent)]:
                if value:
                    clauses.append(f'{column}=?')
                    args.append(value)
            if scrape == 'scraped':
                clauses.append("json_extract(detail,'$.scraped')=1")
            elif scrape == 'not_scraped':
                clauses.append("json_extract(detail,'$.scraped')=0")
            elif scrape == 'incomplete':
                clauses.append("json_extract(detail,'$.scraped')=1 AND json_array_length(detail,'$.missing_images')>0")
            where = ' AND '.join(clauses)
            view.total = db.execute(f'SELECT count(*) FROM entries WHERE {where}', args).fetchone()[0]
            for row in db.execute(f'SELECT detail,present FROM entries WHERE {where} ORDER BY path LIMIT 50 OFFSET ?', [*args, (page - 1) * 50]):
                entry = LibraryEntry.model_validate_json(row['detail'])
                entry.present = bool(row['present'])
                entry.cms_path = config.cms_path(entry.path)
                view.items.append(entry)
        return view

    def routing_entries(self, config):
        """Return only identity fields required to resolve work/season directories."""
        roots = [root for _, root in config.roots]
        if not roots:
            return []
        with self.database() as db:
            scope = ','.join('?' for _ in roots)
            return [LibraryEntry.model_validate_json(row['detail']) for row in db.execute(
                f"SELECT detail FROM entries WHERE present=1 AND entry_type IN ('directory','media') AND root IN ({scope})", roots)]
