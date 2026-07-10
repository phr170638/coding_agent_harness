"""FastAPI 服务 — Agent WebUI 后端，SSE 实时推送步骤事件。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse

from myagent.agent.loop import AgentLoop
from myagent.config.settings import Settings
from myagent.feedback.base import FeedbackChecker
from myagent.guardrails.command import CommandGuardrail
from myagent.guardrails.path import PathGuardrail
from myagent.guardrails.pipeline import GuardrailPipeline
from myagent.llm.bailian import AliBailianBackend
from myagent.tools.base import Tool
from myagent.tools.docker_sandbox import DockerSandbox
from myagent.tools.registry import ToolRegistry

app = FastAPI(title="Coding Agent Harness", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 全局状态
_active_sessions: dict[str, dict] = {}
_active_loops: dict[str, AgentLoop] = {}


def _make_agent_loop(project_path: str, api_key: str) -> AgentLoop:
    """构造带事件回调的 AgentLoop 实例。"""
    settings = Settings(llm_api_key=api_key)

    sandbox = DockerSandbox(project_path=project_path)

    tools = ToolRegistry()
    tools.register(Tool(
        name="read_file", description="读取文件内容",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        execute=lambda path: _read_file(path),
    ))
    tools.register(Tool(
        name="write_file", description="写入文件内容",
        parameters={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
        execute=lambda path, content: _write_file(path, content),
    ))
    tools.register(Tool(
        name="run_shell", description="在沙箱中执行命令",
        parameters={"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
        execute=lambda command: sandbox.run(command),
    ))

    guardrails = GuardrailPipeline()
    guardrails.add(PathGuardrail(project_path))
    guardrails.add(CommandGuardrail())

    feedback: list[FeedbackChecker] = []
    try:
        from myagent.feedback.test_runner import TestFeedbackRunner
        feedback.append(TestFeedbackRunner())
    except Exception:
        pass

    llm = AliBailianBackend(settings=settings, api_key=api_key)
    return AgentLoop(llm_backend=llm, tool_registry=tools, guardrail_pipeline=guardrails, feedback_checkers=feedback, settings=settings)


async def _read_file(path: str) -> dict:
    from myagent.tools.file_io import read_file
    return await read_file(path)


async def _write_file(path: str, content: str) -> dict:
    from myagent.tools.file_io import write_file
    return await write_file(path, content)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/run")
async def start_run(task: str = Query(...), project_path: str = Query(".")):
    """启动任务并返回 session_id。"""
    import uuid
    session_id = uuid.uuid4().hex[:12]

    _active_sessions[session_id] = {"task": task, "project_path": project_path, "status": "starting", "events": []}
    return {"session_id": session_id, "task": task}


@app.get("/api/run/{session_id}/stream")
async def stream_run(session_id: str, request: Request):
    """SSE 端点 — 启动 Agent 并实时推送步骤事件。"""
    session = _active_sessions.get(session_id)
    if not session:
        return StreamingResponse(_error_stream("会话不存在"), media_type="text/event-stream")

    session["status"] = "running"
    project_path = str(Path(session["project_path"]).absolute())
    task = session["task"]

    # 获取 API key
    settings = Settings()
    api_key = settings.llm_api_key
    if not api_key:
        return StreamingResponse(_error_stream("未配置 API Key"), media_type="text/event-stream")

    async def event_gen():
        queue: asyncio.Queue = asyncio.Queue()

        async def on_event(event: dict):
            await queue.put(event)
            await asyncio.sleep(0)  # 让出控制权，确保 SSE 生成器能及时获取事件

        loop = _make_agent_loop(project_path, api_key)
        loop._on_event = on_event
        _active_loops[session_id] = loop

        async def run_agent():
            try:
                state = await loop.run(task, project_path)
                await queue.put({"type": "final", "status": state.status, "steps": state.step_number, "message": state.completion_message})
            except Exception as exc:
                await queue.put({"type": "error", "error": str(exc)})

        agent_task = asyncio.create_task(run_agent())

        try:
            while True:
                if await request.is_disconnected():
                    agent_task.cancel()
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except TimeoutError:
                    yield "event: heartbeat\ndata: {}\n\n"
                    continue

                event_type = event.pop("type", "unknown")
                data = json.dumps(event, ensure_ascii=False)
                yield f"event: {event_type}\ndata: {data}\n\n"

                if event_type in ("final", "error"):
                    break
        finally:
            if not agent_task.done():
                agent_task.cancel()
            session["status"] = "completed"
            _active_loops.pop(session_id, None)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


def _error_stream(message: str):
    async def gen():
        yield f"event: error\ndata: {json.dumps({'error': message}, ensure_ascii=False)}\n\n"
    return gen()


@app.get("/", response_class=HTMLResponse)
async def index():
    """WebUI 前端页面。"""
    frontend = Path(__file__).parent.parent.parent / "frontend" / "index.html"
    if frontend.exists():
        return frontend.read_text(encoding="utf-8")
    return _default_html()


def _default_html() -> str:
    return r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Coding Agent Harness</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:#0d1117;color:#c9d1d9;min-height:100vh}
.header{background:#161b22;border-bottom:1px solid #30363d;padding:16px 24px;display:flex;align-items:center;gap:12px}
.header h1{font-size:18px;color:#f0f6fc}
.main{max-width:900px;margin:24px auto;padding:0 24px}
.input-area{display:flex;gap:12px;margin-bottom:24px}
.input-area input{flex:1;padding:12px 16px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:14px}
.input-area input:focus{outline:none;border-color:#58a6ff}
.input-area button{padding:12px 24px;background:#238636;border:none;border-radius:6px;color:white;font-size:14px;cursor:pointer;white-space:nowrap}
.input-area button:hover{background:#2ea043}
.input-area button:disabled{background:#21262d;color:#484f58;cursor:not-allowed}
.log{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:16px;min-height:300px;max-height:60vh;overflow-y:auto}
.log-item{display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid #21262d;font-size:13px;line-height:1.5}
.log-item:last-child{border-bottom:none}
.icon{flex-shrink:0;width:20px;text-align:center}
.thinking{color:#d29922}.ok{color:#3fb950}.error{color:#f85149}.info{color:#58a6ff}
.guardrail-block{color:#f85149}.guardrail-pass{color:#3fb950}
.step-num{color:#484f58;font-size:11px;min-width:24px}
.content{flex:1;word-break:break-all}
.empty{color:#484f58;text-align:center;padding:40px}
.final{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:16px;margin-top:16px}
.final.completed{border-color:#238636}
.final.failed{border-color:#f85149}
.status{font-size:14px;font-weight:600}
.spinner{display:inline-block;width:14px;height:14px;border:2px solid #30363d;border-top-color:#58a6ff;border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<div class="header"><h1>Coding Agent Harness</h1><span style="color:#484f58;font-size:12px">LLM + Harness</span></div>
<div class="main">
  <div class="input-area">
    <input id="taskInput" type="text" placeholder="输入任务描述，例如：创建一个 hello.py 文件..." />
    <button id="runBtn" onclick="startRun()">开始</button>
  </div>
  <div class="log" id="log"><div class="empty">等待任务…</div></div>
  <div id="finalArea"></div>
</div>
<script>
let eventSource = null;
let stepCount = 0;

document.getElementById('taskInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') startRun();
});

function icon(className) {
  return `<span class="icon ${className}"></span>`;
}

function addLog(type, html) {
  const log = document.getElementById('log');
  if (log.querySelector('.empty')) log.innerHTML = '';
  stepCount++;
  const cls = type === 'error' || type === 'guardrail_block' ? 'error' : type === 'thinking' ? 'thinking' : type === 'done' ? 'ok' : 'info';
  const icons = {thinking:'⏳', llm_response:'\u{1F4AC}', action:'\u{1F527}', guardrail_pass:'✅', guardrail_block:'\u{1F6AB}', tool_result:'✅', tool_error:'❌', feedback:'\u{1F4CB}', done:'✅', parse_error:'❌'};
  const i = icons[type] || '●';
  const div = document.createElement('div');
  div.className = 'log-item ' + cls;
  div.innerHTML = `<span class="step-num">#${stepCount}</span><span class="icon">${i}</span><span class="content ${cls}">${html}</span>`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

async function startRun() {
  const input = document.getElementById('taskInput');
  const btn = document.getElementById('runBtn');
  const task = input.value.trim();
  if (!task) return;

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> 运行中';
  document.getElementById('log').innerHTML = '';
  document.getElementById('finalArea').innerHTML = '';
  stepCount = 0;

  try {
    const res = await fetch(`/api/run?task=${encodeURIComponent(task)}&project_path=.`, {method:'POST'});
    const data = await res.json();
    const sessionId = data.session_id;

    eventSource = new EventSource(`/api/run/${sessionId}/stream`);
    eventSource.addEventListener('thinking', e => addLog('thinking', 'LLM 正在决策下一步…'));
    eventSource.addEventListener('llm_response', e => {const d=JSON.parse(e.data);addLog('llm_response',`LLM 响应 (${d.latency_ms}ms): ${d.content}`)});
    eventSource.addEventListener('parse_error', e => {const d=JSON.parse(e.data);addLog('parse_error',`解析失败: ${d.error}`)});
    eventSource.addEventListener('action', e => {const d=JSON.parse(e.data);addLog('action',`执行: <b>${d.name}</b> ${JSON.stringify(d.parameters)}`)});
    eventSource.addEventListener('guardrail', e => {const d=JSON.parse(e.data);d.allowed ? addLog('guardrail_pass',`护栏通过: ${d.reason}`) : addLog('guardrail_block',`护栏拦截: ${d.reason} [${d.risk_level}]`)});
    eventSource.addEventListener('tool_result', e => {const d=JSON.parse(e.data);addLog('tool_result',`${d.name} 完成: ${d.result}`)});
    eventSource.addEventListener('tool_error', e => {const d=JSON.parse(e.data);addLog('tool_error',`工具错误: ${d.error}`)});
    eventSource.addEventListener('feedback', e => {const d=JSON.parse(e.data);d.passed ? addLog('feedback',`反馈通过 [${d.source}]`) : addLog('tool_error',`反馈失败 [${d.source}]: ${d.summary}`)});
    eventSource.addEventListener('done', e => {const d=JSON.parse(e.data);addLog('done',`任务完成: ${d.message}`)});
    eventSource.addEventListener('final', e => {
      const d = JSON.parse(e.data);
      const cls = d.status === 'completed' ? 'completed' : 'failed';
      document.getElementById('finalArea').innerHTML = `<div class="final ${cls}"><div class="status">${d.status === 'completed' ? '✅ 完成' : '❌ 失败'} (${d.steps} 步)</div><div>${d.message||''}</div></div>`;
      eventSource.close();
      btn.disabled = false;
      btn.textContent = '开始';
    });
    eventSource.addEventListener('error', e => {
      try {const d=JSON.parse(e.data);addLog('error',`错误: ${d.error}`)} catch(_){}
      btn.disabled = false;
      btn.textContent = '开始';
    });
  } catch(err) {
    addLog('error', `请求失败: ${err.message}`);
    btn.disabled = false;
    btn.textContent = '开始';
  }
}
</script>
</body>
</html>"""


def main():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
