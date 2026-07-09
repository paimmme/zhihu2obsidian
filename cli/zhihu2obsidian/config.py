"""Configuration management (~/.zhihu2obsidian/config.yaml)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

CONFIG_DIR = Path.home() / ".zhihu2obsidian"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
DEFAULT_COOKIE_FILE = CONFIG_DIR / "cookies.json"


class Config:
    """项目配置."""

    def __init__(self) -> None:
        self.vault: str = ""
        self.cookie_file: str = str(DEFAULT_COOKIE_FILE)
        self.output_prefix: str = "zhihu2obsidian"
        self.rate_limit_min: float = 1.0
        self.rate_limit_max: float = 3.0
        self.image_concurrency: int = 3
        self.log_level: str = "INFO"
        self.collections: list[int] = []  # empty = sync all
        self.deepseek_api_key: str = ""
        self.knowledge_dir: str = ""  # defaults to output_path / ".knowledge"

    @classmethod
    def load(cls) -> Config:
        cfg = cls()
        if CONFIG_FILE.exists():
            data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))
            if data:
                for key, val in data.items():
                    if hasattr(cfg, key):
                        setattr(cfg, key, val)
        return cfg

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "vault": self.vault,
            "cookie_file": self.cookie_file,
            "output_prefix": self.output_prefix,
            "rate_limit_min": self.rate_limit_min,
            "rate_limit_max": self.rate_limit_max,
            "image_concurrency": self.image_concurrency,
            "log_level": self.log_level,
            "collections": self.collections,
            "deepseek_api_key": self.deepseek_api_key,
            "knowledge_dir": self.knowledge_dir,
        }
        CONFIG_FILE.write_text(
            yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    @property
    def vault_path(self) -> Path:
        return Path(os.path.expanduser(self.vault))

    @property
    def output_path(self) -> Path:
        return self.vault_path / self.output_prefix

    @property
    def knowledge_path(self) -> Path:
        if self.knowledge_dir:
            return Path(os.path.expanduser(self.knowledge_dir))
        return self.output_path / ".knowledge"
