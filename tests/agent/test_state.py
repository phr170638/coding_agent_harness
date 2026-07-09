"""AgentState 测试。"""

from myagent.agent.state import AgentState


class TestAgentState:
    def test_initial_state(self):
        state = AgentState(
            session_id="s1",
            task="实现计算器",
            project_path="/tmp/project",
        )
        assert state.session_id == "s1"
        assert state.task == "实现计算器"
        assert state.project_path == "/tmp/project"
        assert state.step_number == 0
        assert state.status == "running"
        assert state.conversation_history == []
        assert state.consecutive_failures == 0

    def test_default_max_steps(self):
        state = AgentState(
            session_id="s1",
            task="test",
            project_path="/tmp",
        )
        assert state.max_steps == 50

    def test_custom_max_steps(self):
        state = AgentState(
            session_id="s1",
            task="test",
            project_path="/tmp",
            max_steps=10,
        )
        assert state.max_steps == 10

    def test_increment_step(self):
        state = AgentState(
            session_id="s1",
            task="test",
            project_path="/tmp",
        )
        state.increment_step()
        assert state.step_number == 1
        state.increment_step()
        assert state.step_number == 2

    def test_add_to_history(self):
        state = AgentState(
            session_id="s1",
            task="test",
            project_path="/tmp",
        )
        state.add_to_history("assistant", "读取了 main.py", "read_file", '{"ok": true}')
        assert len(state.conversation_history) == 1
        turn = state.conversation_history[0]
        assert turn["role"] == "assistant"
        assert turn["content"] == "读取了 main.py"
        assert turn["action_type"] == "read_file"
        assert turn["action_result"] == '{"ok": true}'

    def test_record_failure(self):
        state = AgentState(
            session_id="s1",
            task="test",
            project_path="/tmp",
        )
        state.record_failure()
        assert state.consecutive_failures == 1
        state.record_failure()
        assert state.consecutive_failures == 2

    def test_record_success_resets_failures(self):
        state = AgentState(
            session_id="s1",
            task="test",
            project_path="/tmp",
        )
        state.record_failure()
        state.record_failure()
        state.record_success()
        assert state.consecutive_failures == 0

    def test_mark_completed(self):
        state = AgentState(
            session_id="s1",
            task="test",
            project_path="/tmp",
        )
        state.mark_completed("任务完成")
        assert state.status == "completed"
        assert state.completion_message == "任务完成"

    def test_mark_failed(self):
        state = AgentState(
            session_id="s1",
            task="test",
            project_path="/tmp",
        )
        state.mark_failed("达到最大步数")
        assert state.status == "failed"
        assert state.completion_message == "达到最大步数"

    def test_mark_blocked(self):
        state = AgentState(
            session_id="s1",
            task="test",
            project_path="/tmp",
        )
        state.mark_blocked("护栏拦截: rm -rf /")
        assert state.status == "blocked"
        assert state.completion_message == "护栏拦截: rm -rf /"
