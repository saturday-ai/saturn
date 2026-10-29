"""Ctrl-C abandons a turn (app/repl.py), but LangGraph runs each node on a worker thread when
it streams tokens, so the node does not stop with the main thread. The turn's cancel token
(core/pause.turn_scope) is what that thread reads: a model stream stops at its next chunk, the
tools node runs no further call, and a model call that still ends late is recorded under its
own run and sequence number — never the next turn's."""

import threading
from contextvars import copy_context

import pytest
from langchain.messages import AIMessage, AIMessageChunk, HumanMessage

from core import pause


def test_a_late_model_call_is_recorded_under_its_own_run_and_sequence(tmp_path):
    import sqlite3

    from langchain_core.outputs import ChatGeneration, LLMResult
    from stores.trace import Tracer

    db = str(tmp_path / "trace.sqlite")
    tracer = Tracer(db)

    def call(handler, uid):
        handler.on_chat_model_start({}, [[HumanMessage(content="q")]], run_id=uid,
                                    metadata={"langgraph_node": "agent"})
        handler.on_llm_end(LLMResult(generations=[[ChatGeneration(message=AIMessage(content="a"))]]),
                           run_id=uid)

    old = tracer.start_run("t1", "first")
    old_handler = tracer.llm_handler(old)
    call(old_handler, "a1")
    new = tracer.start_run("t2", "second")   # the user pressed Ctrl-C and asked again
    call(old_handler, "a2")                  # the abandoned turn's call ends late
    call(tracer.llm_handler(new), "b1")
    with sqlite3.connect(db) as c:
        rows = c.execute("SELECT run_id, seq FROM llm_calls ORDER BY id").fetchall()
    assert rows == [(old, 1), (old, 2), (new, 1)]


def test_leaving_a_turn_by_an_exception_cancels_the_work_it_started():
    started, seen = threading.Event(), {}

    def worker():
        started.set()
        seen["cancelled"] = pause.wait_cancelled(2.0)

    with pytest.raises(KeyboardInterrupt):
        with pause.turn_scope():
            t = threading.Thread(target=copy_context().run, args=(worker,))
            t.start()
            started.wait(1.0)
            assert not pause.turn_cancelled()
            raise KeyboardInterrupt
    t.join(3.0)
    assert seen["cancelled"] is True
    assert not pause.turn_cancelled()        # outside any turn: nothing is cancelled
    with pause.turn_scope():
        assert not pause.turn_cancelled()    # the next turn starts clean


def test_run_turn_cancels_its_nodes_when_the_caller_stops_listening():
    """The REPL's Ctrl-C lands in run_turn's stream loop (here: in on_update)."""
    from app.turn import run_turn

    seen = {}

    class Graph:
        def stream(self, *_a, **_k):
            def node():
                seen["cancelled"] = pause.wait_cancelled(2.0)
            seen["thread"] = threading.Thread(target=copy_context().run, args=(node,))
            seen["thread"].start()
            yield "updates", {"agent": {}}

    def interrupt(*_a):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_turn(Graph(), {"current_query": "q"}, {}, approver=None, on_update=interrupt)
    seen["thread"].join(3.0)
    assert seen["cancelled"] is True


def test_a_model_stream_stops_when_its_turn_is_cancelled(monkeypatch):
    from nodes import agent

    seen = {"read": 0, "closed": False}

    class Model:
        def bind_tools(self, _tools):
            return self

    def fake_stream(*_a, **_k):
        try:
            for text in ["one ", "two ", "three"]:
                seen["read"] += 1
                yield AIMessageChunk(content=text)
        finally:
            seen["closed"] = True

    monkeypatch.setattr(agent, "llm_stream", fake_stream)
    monkeypatch.setattr(agent, "get_model", lambda: Model())
    monkeypatch.setattr(agent, "model_tag", lambda: "m")
    with pause.turn_scope() as turn:
        turn.set()
        with pytest.raises(pause.TurnCancelled):
            agent._generate([HumanMessage(content="q")], tools=True)
    assert seen == {"read": 1, "closed": True}


def test_the_tools_node_runs_nothing_for_a_cancelled_turn(monkeypatch):
    import nodes.tools as tn

    ran = []

    class Tool:
        def invoke(self, args):
            ran.append(args)
            return "x"

    monkeypatch.setitem(tn.tools_by_name, "read_file", Tool())
    msg = AIMessage(content="", tool_calls=[
        {"name": "read_file", "args": {"file_path": "a"}, "id": "c1"},
        {"name": "read_file", "args": {"file_path": "b"}, "id": "c2"}])
    with pause.turn_scope() as turn:
        turn.set()
        with pytest.raises(pause.TurnCancelled):
            tn.tool_node({"messages": [msg]})
    assert ran == []


def test_a_real_graph_node_sees_its_turn_cancelled():
    """The premise, on LangGraph itself: streaming tokens runs the node on a worker thread that
    outlives Ctrl-C in the main thread, and that thread reads the turn's token."""
    from typing import TypedDict

    from langgraph.config import get_stream_writer
    from langgraph.graph import END, START, StateGraph

    from app.turn import run_turn

    seen = {"done": threading.Event()}

    class S(TypedDict, total=False):
        x: int

    def node(_state):
        seen["thread"] = threading.current_thread()
        get_stream_writer()({"type": "thinking", "phase": "start"})
        seen["cancelled"] = pause.wait_cancelled(2.0)
        seen["done"].set()
        return {"x": 1}

    g = StateGraph(S)
    g.add_node("agent", node)
    g.add_edge(START, "agent")
    g.add_edge("agent", END)

    def ctrl_c(_started):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_turn(g.compile(), {"x": 0}, {}, approver=None, on_thinking=ctrl_c)
    assert seen["done"].wait(3.0)
    assert seen["thread"] is not threading.main_thread() and seen["cancelled"] is True


def test_ctrl_c_inside_langgraph_cancels_the_node_before_langgraph_waits_for_it():
    """The usual Ctrl-C lands while the main thread waits inside graph.stream, whose cleanup
    waits for the running node — the token must already be set when that wait begins, or the
    turn hangs until the model finishes (run 89: 23 s after Ctrl-C)."""
    import os
    import signal
    import time
    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph

    from app.turn import run_turn

    seen = {}

    class S(TypedDict, total=False):
        x: int

    def node(_state):
        threading.Timer(0.1, os.kill, (os.getpid(), signal.SIGINT)).start()
        seen["cancelled"] = pause.wait_cancelled(5.0)
        return {"x": 1}

    g = StateGraph(S)
    g.add_node("agent", node)
    g.add_edge(START, "agent")
    g.add_edge("agent", END)
    began = time.perf_counter()
    with pytest.raises(KeyboardInterrupt):
        run_turn(g.compile(), {"x": 0}, {}, approver=None, on_thinking=lambda _s: None)
    assert seen["cancelled"] is True and time.perf_counter() - began < 2.0
    assert signal.getsignal(signal.SIGINT) is signal.default_int_handler  # put back
