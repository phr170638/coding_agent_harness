"""停机条件测试。"""

from myagent.agent.state import AgentState
from myagent.agent.stop import (
    should_stop,
    stop_when_consecutive_failures,
    stop_when_max_steps,
    stop_when_task_completed,
)


def make_state(**kwargs) -> AgentState:
    defaults = {
        "session_id": "s1",
        "task": "test",
        "project_path": "/tmp",
        "max_steps": 10,
        "max_consecutive_failures": 3,
    }
    defaults.update(kwargs)
    return AgentState(**defaults)


class TestStopWhenMaxSteps:
    def test_under_max_not_stop(self):
        state = make_state()
        state.increment_step()  # step 1
        assert not stop_when_max_steps(state)

    def test_at_max_stops(self):
        state = make_state(max_steps=2)
        state.increment_step()  # step 1
        state.increment_step()  # step 2
        assert stop_when_max_steps(state)

    def test_over_max_stops(self):
        state = make_state(max_steps=1)
        state.increment_step()
        state.increment_step()  # step 2, max is 1
        assert stop_when_max_steps(state)


class TestStopWhenTaskCompleted:
    def test_running_not_stop(self):
        state = make_state()
        assert not stop_when_task_completed(state)

    def test_completed_stops(self):
        state = make_state()
        state.mark_completed("done")
        assert stop_when_task_completed(state)

    def test_failed_stops(self):
        state = make_state()
        state.mark_failed("error")
        assert stop_when_task_completed(state)

    def test_blocked_stops(self):
        state = make_state()
        state.mark_blocked("blocked")
        assert stop_when_task_completed(state)


class TestStopWhenConsecutiveFailures:
    def test_no_failures_not_stop(self):
        state = make_state()
        assert not stop_when_consecutive_failures(state)

    def test_one_failure_not_stop(self):
        state = make_state()
        state.record_failure()
        assert not stop_when_consecutive_failures(state)

    def test_three_failures_stops(self):
        state = make_state()
        for _ in range(3):
            state.record_failure()
        assert stop_when_consecutive_failures(state)

    def test_failure_then_success_resets(self):
        state = make_state()
        state.record_failure()
        state.record_failure()
        state.record_success()
        state.record_failure()
        assert not stop_when_consecutive_failures(state)


class TestShouldStop:
    def test_normal_state_continues(self):
        state = make_state()
        assert not should_stop(state)

    def test_max_steps_stops(self):
        state = make_state(max_steps=1)
        state.increment_step()
        assert should_stop(state)

    def test_completed_stops(self):
        state = make_state()
        state.mark_completed("done")
        assert should_stop(state)

    def test_consecutive_failures_stops(self):
        state = make_state()
        for _ in range(3):
            state.record_failure()
        assert should_stop(state)
