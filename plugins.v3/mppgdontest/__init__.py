"""MoviePilot V3 安装与配置测试插件。"""

from typing import Any

from app.sdk.plugin import _PluginBase


class MppgdonTest(_PluginBase):
    """用最小配置和详情页验证第三方插件安装链路。"""

    plugin_name = "MPPGDON 安装测试"
    plugin_desc = "验证 MoviePilot V3 插件安装、配置保存和启停。"
    plugin_icon = "https://raw.githubusercontent.com/jxxghp/MoviePilot-Plugins/main/icons/Moviepilot_A.png"
    plugin_version = "0.1.0"
    plugin_author = "xdong125"
    author_url = "https://github.com/xdong125"
    plugin_config_prefix = "mppgdontest_"
    plugin_order = 50
    auth_level = 1

    _enabled = False
    _message = "Hello MoviePilot V3，安装测试成功！"

    def init_plugin(self, config: dict | None = None) -> None:
        """每次保存或重载时重新读取配置，不启动后台任务。"""
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._message = str(config.get("message") or "Hello MoviePilot V3，安装测试成功！")

    def get_state(self) -> bool:
        """向宿主返回启用状态。"""
        return self._enabled

    @staticmethod
    def get_command() -> list[dict[str, Any]]:
        """测试插件不注册远程命令。"""
        return []

    def get_api(self) -> list[dict[str, Any]]:
        """测试插件不注册额外 API。"""
        return []

    def get_form(self) -> tuple[list[dict], dict[str, Any]]:
        """提供启用开关与展示文本，配置由宿主保存。"""
        return [{
            "component": "VForm",
            "content": [
                {
                    "component": "VAlert",
                    "props": {
                        "type": "info", "variant": "tonal", "class": "mb-4",
                        "text": "安装测试 v0.1.0：保存配置后打开详情页，检查文本和启用状态。",
                    },
                },
                {
                    "component": "VSwitch",
                    "props": {"model": "enabled", "label": "启用测试插件"},
                },
                {
                    "component": "VTextField",
                    "props": {"model": "message", "label": "测试展示文本"},
                },
            ],
        }], {
            "enabled": False,
            "message": "Hello MoviePilot V3，安装测试成功！",
        }

    def get_page(self) -> list[dict]:
        """通过普通文本组件展示加载结果和保存后的配置。"""
        return [
            {
                "component": "VAlert",
                "props": {
                    "type": "success", "variant": "tonal", "class": "mb-4",
                    "text": f"MPPGDON 安装测试 v{self.plugin_version} 已加载；状态：{'已启用' if self._enabled else '已停用'}。",
                },
            },
            {
                "component": "VAlert",
                "props": {"type": "info", "variant": "tonal", "text": self._message},
            },
        ]

    def stop_service(self) -> None:
        """停用时重置状态；本插件没有线程、定时器或连接需要清理。"""
        self._enabled = False
