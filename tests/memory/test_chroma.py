"""ChromaDB 知识存储测试。"""

import pytest

from myagent.config.settings import Settings
from myagent.memory.chroma import KnowledgeStore


@pytest.mark.skipif(
    True,  # ChromaDB 测试默认跳过（embedding API 不可用）
    reason="ChromaDB 需要 embedding API，暂时跳过",
)
class TestKnowledgeStore:
    def test_add_and_search(self, temp_dir):
        settings = Settings(chroma_db_path=str(temp_dir / "chroma"))
        store = KnowledgeStore(settings)

        if not store._enabled:
            pytest.skip("ChromaDB 不可用")

        store.add("本项目使用 pytest 作为测试框架", {"type": "convention"})
        results = store.search("测试框架")
        assert len(results) > 0

    def test_search_empty_store(self, temp_dir):
        settings = Settings(chroma_db_path=str(temp_dir / "chroma"))
        store = KnowledgeStore(settings)

        if not store._enabled:
            pytest.skip("ChromaDB 不可用")

        results = store.search("nothing")
        assert results == []

    def test_count(self, temp_dir):
        settings = Settings(chroma_db_path=str(temp_dir / "chroma"))
        store = KnowledgeStore(settings)

        if not store._enabled:
            pytest.skip("ChromaDB 不可用")

        assert store.count() >= 0
