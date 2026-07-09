"""SQLite 会话存储测试。"""

import pytest

from myagent.memory.sqlite import SessionStore


@pytest.fixture
def store(temp_dir):
    s = SessionStore(db_path=str(temp_dir / "test.db"))
    yield s
    s.close()


class TestSessionStore:
    def test_create_and_query_session(self, store):
        store.create_session("s1", "实现计算器", "/tmp/project")
        turns = store.get_recent_turns("s1")
        assert turns == []

    def test_record_and_retrieve_turns(self, store):
        store.create_session("s2", "修复bug", "/tmp/project")
        store.record_turn("s2", 1, "assistant", "读取了 main.py", action_type="read_file")
        store.record_turn("s2", 2, "assistant", "修复完成", action_type="write_file")

        turns = store.get_recent_turns("s2")
        assert len(turns) == 2
        assert turns[0]["step_number"] == 1
        assert turns[1]["step_number"] == 2

    def test_get_recent_turns_respects_limit(self, store):
        store.create_session("s3", "task", "/tmp/project")
        for i in range(30):
            store.record_turn("s3", i, "assistant", f"step {i}")

        turns = store.get_recent_turns("s3", limit=10)
        assert len(turns) == 10

    def test_update_session_status(self, store):
        store.create_session("s4", "task", "/tmp/project")
        store.update_session_status("s4", "completed")
        # 不抛异常即成功

    def test_conventions_crud(self, store):
        store.set_convention("test_framework", "pytest")
        assert store.get_convention("test_framework") == "pytest"

        store.set_convention("test_framework", "unittest")
        assert store.get_convention("test_framework") == "unittest"

    def test_get_all_conventions(self, store):
        store.set_convention("a", "1")
        store.set_convention("b", "2")
        all_c = store.get_all_conventions()
        assert all_c == {"a": "1", "b": "2"}

    def test_db_persistence(self, temp_dir):
        db_path = str(temp_dir / "persist.db")
        store1 = SessionStore(db_path=db_path)
        store1.set_convention("language", "python")
        store1.create_session("s1", "test", "/tmp")
        store1.close()

        # 重新打开，数据应在
        store2 = SessionStore(db_path=db_path)
        assert store2.get_convention("language") == "python"
        store2.close()
