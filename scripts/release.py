"""检查插件元数据并生成 MoviePilot 规范的 Release 资产。"""

import ast
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    """只打包运行源码与全部联邦产物，不包含测试或开发依赖。"""
    package = json.loads((ROOT / 'package.v3.json').read_text(encoding='utf-8'))
    plugin_id, meta = next(iter(package.items()))
    folder = ROOT / 'plugins.v3' / plugin_id.lower()
    module = ast.parse((folder / '__init__.py').read_text(encoding='utf-8'))
    plugin = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == plugin_id)
    attributes = {node.targets[0].id: ast.literal_eval(node.value) for node in plugin.body
                  if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                  and isinstance(node.value, ast.Constant)}
    assert attributes['plugin_version'] == meta['version']
    assert attributes['plugin_name'] == meta['name']
    assert next(iter(meta['history'])) == 'v' + meta['version']
    assert meta['release'] is True
    assert (folder / 'dist/assets/remoteEntry.js').is_file()
    for source in folder.glob('*.py'):
        compile(source.read_text(encoding='utf-8'), str(source), 'exec')
    target = ROOT / 'release-out'
    target.mkdir(exist_ok=True)
    tag = f"{plugin_id}_v{meta['version']}"
    archive = target / f'{tag.lower()}.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as package_zip:
        for source in sorted(folder.rglob('*')):
            if source.is_file() and '__pycache__' not in source.parts:
                package_zip.write(source, source.relative_to(folder).as_posix())
    with zipfile.ZipFile(archive) as package_zip:
        assert '__init__.py' in package_zip.namelist()
        assert 'search.py' in package_zip.namelist()
        assert 'dist/assets/remoteEntry.js' in package_zip.namelist()
        assert not any('node_modules' in n or '__pycache__' in n or n.startswith('tests/') for n in package_zip.namelist())
    (target / 'notes.md').write_text(meta['history']['v' + meta['version']] + '\n\nMoviePilot V3 测试版。使用方法见仓库 README。\n', encoding='utf-8')
    print(f'{tag}\n{archive.relative_to(ROOT).as_posix()}')


if __name__ == '__main__':
    main()
