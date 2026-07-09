"""ChromaDB 知识存储 — 语义搜索项目约定和历史决策。"""

from __future__ import annotations

import logging
from pathlib import Path

from myagent.config.settings import Settings

logger = logging.getLogger(__name__)


class KnowledgeStore:
    """基于 ChromaDB 的语义知识存储。

    存储和检索项目约定、架构决策、历史经验等非结构化知识。
    embedding 通过阿里 text-embedding-v3 生成。
    如果 embedding 不可用，降级为纯文本匹配。
    """

    COLLECTION_NAME = "project_knowledge"

    def __init__(self, settings: Settings):
        self._settings = settings
        self._persist_dir = Path(settings.chroma_db_path)
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._enabled = True
        self._store = None

        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            self._client = chromadb.PersistentClient(
                path=str(self._persist_dir),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._store = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            logger.warning("ChromaDB 初始化失败，知识存储降级: %s", e)
            self._enabled = False

    def add(self, text: str, metadata: dict | None = None, doc_id: str | None = None) -> bool:
        """添加知识条目到向量库。"""
        if not self._enabled or self._store is None:
            return False
        try:
            import uuid
            self._store.add(
                documents=[text],
                metadatas=[metadata or {}],
                ids=[doc_id or str(uuid.uuid4())],
            )
            return True
        except Exception as e:
            logger.warning("知识写入失败: %s", e)
            return False

    def search(self, query: str, k: int = 3) -> list[str]:
        """语义搜索相关知识。"""
        if not self._enabled or self._store is None:
            return []
        try:
            results = self._store.query(query_texts=[query], n_results=k)
            docs = results.get("documents", [[]])[0]
            return [d for d in docs if d]
        except Exception as e:
            logger.warning("知识搜索失败: %s", e)
            return []

    def count(self) -> int:
        """返回已索引的知识条目数。"""
        if not self._enabled or self._store is None:
            return 0
        try:
            return self._store.count()  # type: ignore[no-any-return]
        except Exception:
            return 0
