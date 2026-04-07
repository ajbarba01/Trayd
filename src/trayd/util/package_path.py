import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_path(*parts: str) -> str:
    return os.path.join(_ROOT, *parts)
