"""宿主边界 Mock 测试；不代替 MoviePilot V3 实机安装验证。"""

import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "plugins.v3/mppgdontest/__init__.py"


def load_plugin():
    """通过生产模块名导入插件，仅替换当前测试不使用的宿主基类。"""
    sdk = types.ModuleType("app.sdk.plugin")
    sdk._PluginBase = type("_PluginBase", (), {})
    name = "app.plugins.mppgdontest"
    spec = importlib.util.spec_from_file_location(name, SOURCE)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.sdk.plugin": sdk, name: module}):
        spec.loader.exec_module(module)
    return module.MppgdonTest


Plugin = load_plugin()


class PluginTests(unittest.TestCase):
    """验证索引一致性、配置生命周期和页面结果。"""

    def test_default_disabled(self):
        plugin = Plugin()
        plugin.init_plugin()
        self.assertFalse(plugin.get_state())
        self.assertIn("Hello MoviePilot V3", plugin.get_page()[1]["props"]["text"])

    def test_configuration_visible_on_page(self):
        plugin = Plugin()
        config = {"enabled": True, "message": "我的 MP 插件安装成功"}
        plugin.init_plugin(config)
        self.assertTrue(plugin.get_state())
        self.assertIn("已启用", plugin.get_page()[0]["props"]["text"])
        self.assertEqual(config["message"], plugin.get_page()[1]["props"]["text"])
        self.assertEqual(config, {"enabled": True, "message": "我的 MP 插件安装成功"})

    def test_stop_and_reinitialization(self):
        plugin = Plugin()
        plugin.init_plugin({"enabled": True, "message": "first"})
        plugin.stop_service()
        plugin.stop_service()
        self.assertFalse(plugin.get_state())
        plugin.init_plugin({"enabled": True, "message": "second"})
        self.assertTrue(plugin.get_state())
        plugin.init_plugin({})
        self.assertFalse(plugin.get_state())
        self.assertNotEqual("second", plugin.get_page()[1]["props"]["text"])

    def test_instances_have_separate_state(self):
        first, second = Plugin(), Plugin()
        first.init_plugin({"enabled": True, "message": "first"})
        second.init_plugin({"enabled": False, "message": "second"})
        first.stop_service()
        self.assertEqual("second", second.get_page()[1]["props"]["text"])
        self.assertFalse(second.get_state())

    def test_plain_text_not_html(self):
        plugin = Plugin()
        message = '<script>alert("test")</script>'
        plugin.init_plugin({"message": message})
        page = plugin.get_page()
        self.assertEqual(message, page[1]["props"]["text"])
        self.assertNotIn("innerHTML", json.dumps(page))
        self.assertNotIn("v-html", json.dumps(page))

    def test_form_models_and_empty_extensions(self):
        form, defaults = Plugin().get_form()
        models = {item.get("props", {}).get("model") for item in form[0]["content"]}
        self.assertTrue(set(defaults).issubset(models))
        self.assertFalse(defaults["enabled"])
        self.assertEqual([], Plugin().get_api())
        self.assertEqual([], Plugin.get_command())
        json.dumps(form, ensure_ascii=False)

    def test_market_metadata(self):
        packages = json.loads((ROOT / "package.v3.json").read_text(encoding="utf-8"))
        self.assertEqual([Plugin.__name__], list(packages))
        meta = packages[Plugin.__name__]
        for key, attr in [("name", "plugin_name"), ("description", "plugin_desc"),
                          ("version", "plugin_version"), ("icon", "plugin_icon"),
                          ("author", "plugin_author"), ("level", "auth_level")]:
            self.assertEqual(meta[key], getattr(Plugin, attr))
        self.assertEqual("v" + Plugin.plugin_version, next(iter(meta["history"])))
        self.assertEqual(Plugin.__name__.lower(), SOURCE.parent.name)
        self.assertFalse(meta["release"])
        for name in ["package.json", "package.v2.json"]:
            self.assertEqual({}, json.loads((ROOT / name).read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
