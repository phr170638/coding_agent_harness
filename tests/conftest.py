"""pytest 共享 fixtures。"""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """创建临时目录，测试结束后自动清理。"""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def temp_project(temp_dir):
    """创建模拟项目目录，含 pyproject.toml 和 src 目录。"""
    (temp_dir / "pyproject.toml").touch()
    (temp_dir / "src").mkdir()
    return temp_dir
