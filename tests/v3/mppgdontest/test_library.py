"""Local fixtures only: no user library, host database or network access."""
from pathlib import Path
import inspect
import tempfile
import unittest
from unittest.mock import patch

from test_plugin import LIBRARY as lib, MODULE, SEARCH, ROOT


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(self.enterContext(tempfile.TemporaryDirectory(dir=ROOT / 'release-out'))).resolve()
        self.movies = self.base / '电影'
        self.shows = self.base / '电视剧'
        self.data = self.base / 'plugin-data'
        for path in (self.movies, self.shows, self.data):
            path.mkdir()
        self.index = lib.LibraryIndex(lambda: self.data)
        self.config = lib.LibraryConfig.from_settings({
            'library_movie_root': str(self.movies), 'library_tv_root': str(self.shows),
            'library_path_mapping': str(self.base) + '#/media',
        })

    def put(self, path, content='fixture'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def scan(self):
        self.index.start(self.config)
        self.index._thread.join(5)
        self.assertFalse(self.index._thread.is_alive())
        view = self.index.view(self.config)
        self.assertEqual('complete', view.scan.status, view.scan.errors)
        return view

    def test_independent_show_episode_movie_and_missing_images(self):
        show = self.shows / '无声的回响'
        season = show / 'S01'
        self.put(show / 'tvshow.nfo', '<tvshow><title>无声的回响</title><uniqueid type="tmdb">123</uniqueid></tvshow>')
        self.put(show / 'poster.jpg')
        first = self.put(season / '无声的回响.S01E01.strm', 'https://private.invalid/play?token=do-not-store')
        self.put(first.with_suffix('.nfo'), '<episodedetails><title>第一集</title><season>1</season><episode>1</episode></episodedetails>')
        self.put(season / '无声的回响.S01E02.strm')
        self.put(season / '无声的回响.S01E02.jpg')
        self.put(season / '无声的回响.S01E03.strm')
        self.put(season / '无声的回响.S01E03.nfo', '<broken>')
        movie = self.put(self.movies / '示例电影 (2026)' / '示例电影.strm')
        self.put(movie.with_suffix('.nfo'), '<movie><title>示例电影</title><year>2026</year></movie>')
        (self.shows / '未刮削剧').mkdir()
        view = self.scan()
        self.assertEqual((4, 2, 2, 2), tuple(view.summary[k] for k in ('media', 'scraped', 'not_scraped', 'incomplete')))
        entries = {Path(item.path).name: item for item in view.items}
        self.assertTrue(entries[first.name].scraped)
        self.assertEqual(['thumbnail'], entries[first.name].missing_images)
        self.assertFalse(entries['无声的回响.S01E02.strm'].scraped)
        self.assertEqual('invalid', entries['无声的回响.S01E03.strm'].nfo_state)
        directory = self.index.view(self.config, entry_type='directory', keyword='无声的回响').items
        show_row = next(item for item in directory if item.path == str(show))
        self.assertTrue(show_row.scraped)
        self.assertEqual(['background', 'logo'], show_row.missing_images)
        self.assertEqual('123', show_row.tmdb_id)
        untagged = self.index.view(self.config, entry_type='directory', keyword='未刮削剧').items[0]
        self.assertFalse(untagged.scraped)
        self.assertEqual('missing', untagged.nfo_state)
        self.assertEqual('/media/电视剧/无声的回响/S01/无声的回响.S01E01.strm', entries[first.name].cms_path)
        self.assertNotIn(b'do-not-store', (self.data / 'media-library.sqlite3').read_bytes())

    def test_incremental_nfo_cache_reacts_to_file_and_image_changes(self):
        movie = self.put(self.movies / '示例 (2026)' / '示例.strm')
        nfo = self.put(movie.with_suffix('.nfo'), '<movie><title>示例</title></movie>')
        self.scan()
        with patch.object(lib, '_parse_nfo', side_effect=AssertionError('unchanged NFO reread')):
            view = self.scan()
        self.assertEqual((0, 1), (view.scan.parsed_nfo, view.scan.reused_nfo))
        self.put(movie.parent / 'poster.jpg')
        self.put(movie.parent / 'backdrop.jpg')
        self.assertEqual(0, self.scan().summary['incomplete'])
        self.put(nfo, '<movie><title>修改后的片名</title><year>2026</year></movie>')
        view = self.scan()
        self.assertEqual(1, view.scan.parsed_nfo)
        self.assertEqual('修改后的片名', view.items[0].title)
        movie.unlink()
        self.assertEqual(0, self.scan().total)
        missing = self.index.view(self.config, include_missing=True)
        self.assertEqual(1, missing.total)
        self.assertFalse(missing.items[0].present)

    def test_offline_root_keeps_inventory_and_xml_cannot_define_entities(self):
        movie = self.put(self.movies / '示例 (2026)' / '示例.strm')
        self.put(movie.with_suffix('.nfo'), '<!DOCTYPE movie [<!ENTITY x "example">]><movie><title>&x;</title></movie>')
        view = self.scan()
        self.assertFalse(view.items[0].scraped)
        self.movies.rename(self.base / 'unmounted')
        self.index.start(self.config)
        self.index._thread.join(5)
        view = self.index.view(self.config)
        self.assertEqual('partial', view.scan.status)
        self.assertTrue(view.items[0].present)
        self.movies.mkdir()
        self.index.start(self.config)
        self.index._thread.join(5)
        view = self.index.view(self.config)
        self.assertEqual('partial', view.scan.status)
        self.assertTrue(view.items[0].present)
        # Reopening the index does not launch another scan or reset the inventory.
        self.assertEqual(1, lib.LibraryIndex(lambda: self.data).view(self.config).total)

    def test_prefix_mapping_boundaries_and_admin_api_contract(self):
        source = str(self.base / 'mp')
        config = lib.LibraryConfig.from_settings({'library_path_mapping': source + '#/media\n' + source + '/tv#/media/shows'})
        self.assertEqual('/media/shows/Test/S01', config.cms_path(source + '/tv/Test/S01'))
        self.assertEqual(str(Path(source + '-other') / 'test'), config.cms_path(source + '-other/test'))
        with self.assertRaises(SEARCH.SearchError):
            lib.LibraryConfig.from_settings({'library_movie_root': str(self.movies), 'library_tv_root': str(self.movies / 'nested')})
        with self.assertRaises(SEARCH.SearchError):
            lib.LibraryConfig.from_settings({'library_path_mapping': source + '#/media/../etc'})
        plugin = MODULE.MppgdonTest()
        plugin.init_plugin({'enabled': True})
        for route in plugin.get_api():
            if route['path'].startswith('/library'):
                self.assertEqual('bear', route['auth'])
                self.assertIs(MODULE.get_current_active_superuser, inspect.signature(route['endpoint']).parameters['_admin'].default)
                self.assertIn('data', route['response_model'].model_fields)


if __name__ == '__main__':
    unittest.main()
