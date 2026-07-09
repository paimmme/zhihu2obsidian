"""平台适配器注册中心."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import Platform

_registry: dict[str, type["Platform"]] = {}


def register(name: str):
    """装饰器：注册平台适配器."""
    def decorator(cls: type["Platform"]) -> type["Platform"]:
        _registry[name] = cls
        return cls
    return decorator


def get_platform(name: str) -> type["Platform"]:
    """按名称获取平台类."""
    cls = _registry.get(name)
    if not cls:
        raise ValueError(
            f"未知平台: {name}。可用: {', '.join(list_platforms())}"
        )
    return cls


def list_platforms() -> list[str]:
    """列出所有已注册平台."""
    return list(_registry.keys())
