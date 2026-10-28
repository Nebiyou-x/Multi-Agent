"""Tests for the Phase 2 tools: code_execution, sql_query, web_search.

All network/db/docker access is mocked - these run with no services up.
"""

import base64
import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from packages.tools.registry import tool_registry


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
def test_registry_has_all_phase2_tools():
    assert set(tool_registry) == {"http_fetch", "code_execution", "sql_query", "web_search"}


# ---------------------------------------------------------------------------
# code_execution
# ---------------------------------------------------------------------------
class TestCodeExecution:
    async def test_accepts_bare_string(self, monkeypatch):
        calls = {}

        async def fake_run(code, input_files=None, **kw):
            calls["code"] = code
            return {"exit_code": 0, "artifacts": [], "stdout": "", "stderr": ""}

        fake_manager = SimpleNamespace(run_code=fake_run)
        with patch("packages.tools.code_execution.get_sandbox_manager", AsyncMock(return_value=fake_manager)):
            res = await tool_registry["code_execution"]("print('hi')")
        assert calls["code"] == "print('hi')"
        assert res["exit_code"] == 0

    async def test_accepts_dict_with_input_files(self):
        captured = {}

        async def fake_run(code, input_files=None, **kw):
            captured["files"] = input_files
            return {"exit_code": 0, "artifacts": [{"name": "chart.png", "size": 10}], "stdout": "x", "stderr": ""}

        fake_manager = SimpleNamespace(run_code=fake_run)
        with patch("packages.tools.code_execution.get_sandbox_manager", AsyncMock(return_value=fake_manager)):
            res = await tool_registry["code_execution"]({
                "code": "import pandas as pd",
                "input_files": {"data.json": {"rows": [1]}},
            })
        assert captured["files"] == {"data.json": {"rows": [1]}}
        assert res["artifact_names"] == ["chart.png"]

    async def test_error_set_when_exit_nonzero(self):
        async def fake_run(code, input_files=None, **kw):
            return {"exit_code": 1, "artifacts": [], "stdout": "", "stderr": "boom"}

        fake_manager = SimpleNamespace(run_code=fake_run)
        with patch("packages.tools.code_execution.get_sandbox_manager", AsyncMock(return_value=fake_manager)):
            res = await tool_registry["code_execution"]({"code": "x=1"})
        assert "exited 1" in res["error"]

    async def test_error_set_when_timed_out(self):
        async def fake_run(code, input_files=None, **kw):
            return {"exit_code": None, "timed_out": True, "artifacts": [], "stdout": "", "stderr": ""}

        fake_manager = SimpleNamespace(run_code=fake_run)
        with patch("packages.tools.code_execution.get_sandbox_manager", AsyncMock(return_value=fake_manager)):
            res = await tool_registry["code_execution"]("while True: pass")
        assert "timeout" in res["error"]

    async def test_missing_code_returns_error(self):
        res = await tool_registry["code_execution"]({"no_code_here": 1})
        assert "error" in res


# ---------------------------------------------------------------------------
# sql_query
#
# The module does `import psycopg2` at top level, so we inject a fake module
# into sys.modules BEFORE importing the tool (or, if psycopg2 happens to be
# installed, we patch the real name used inside the module).
# ---------------------------------------------------------------------------
import types


def _make_fake_psycopg2(columns, rows, *, reject_writes=False):
    """Build a fake psycopg2 module: connect() returns a conn whose cursor
    serves SELECTs from `rows` and optionally rejects non-SET/SELECT
    statements as ReadOnlySqlTransaction."""

    class _Error(Exception):
        pass

    class ReadOnlySqlTransaction(_Error):
        pass

    class QueryCanceled(_Error):
        pass

    class _Cursor:
        def __init__(self):
            self.description = None
            self._rows = [r for r in rows]

        def execute(self, query, params=None):
            q = query.strip().upper()
            if q.startswith(("SELECT", "WITH", "SET")):
                if q.startswith(("SELECT", "WITH")):
                    self.description = [SimpleNamespace(name=c) for c in columns]
                return
            if reject_writes:
                raise ReadOnlySqlTransaction("write command not allowed on read-only session")

        def fetchmany(self, n):
            out = self._rows[:n]
            self._rows = self._rows[n:]
            return out

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Conn:
        def set_session(self, readonly=False):
            self.readonly = readonly

        def cursor(self):
            return _Cursor()

        def rollback(self):
            pass

        def close(self):
            pass

    mod = types.ModuleType("psycopg2")
    mod.connect = lambda url, **kw: _Conn()
    mod.Error = _Error
    mod.errors = SimpleNamespace(
        ReadOnlySqlTransaction=ReadOnlySqlTransaction,
        QueryCanceled=QueryCanceled,
    )
    return mod


def _patch_sql_query(fake_mod, monkeypatch):
    """Point packages.tools.sql_query at the fake psycopg2 module."""
    import packages.tools.sql_query as sql_mod
    monkeypatch.setattr(sql_mod, "psycopg2", fake_mod, raising=False)


class TestSqlQuery:
    async def test_select_returns_rows(self, monkeypatch):
        import packages.tools.sql_query as sql_mod
        monkeypatch.setenv("DATABASE_URL", "postgresql://x")
        monkeypatch.setenv("SQL_MAX_ROWS", "100")
        fake_mod = _make_fake_psycopg2(
            ["year", "value"], [[2024, 3.1], [2025, 4.2], [2026, 5.0]]
        )
        _patch_sql_query(fake_mod, monkeypatch)
        res = await sql_mod.sql_query({"query": "SELECT year, value FROM data.inflation"})
        assert res["columns"] == ["year", "value"]
        assert res["row_count"] == 3
        assert res["truncated"] is False
        assert res["rows"] == [[2024, 3.1], [2025, 4.2], [2026, 5.0]]

    async def test_row_limit_truncates(self, monkeypatch):
        import packages.tools.sql_query as sql_mod
        monkeypatch.setenv("DATABASE_URL", "postgresql://x")
        monkeypatch.setenv("SQL_MAX_ROWS", "2")
        fake_mod = _make_fake_psycopg2(["id"], [[i] for i in range(10)])
        _patch_sql_query(fake_mod, monkeypatch)
        res = await sql_mod.sql_query({"query": "SELECT id FROM data.t"})
        assert res["row_count"] == 2
        assert res["truncated"] is True
        assert res["limit"] == 2

    async def test_write_rejected_cleanly(self, monkeypatch):
        import packages.tools.sql_query as sql_mod
        monkeypatch.setenv("DATABASE_URL", "postgresql://x")
        fake_mod = _make_fake_psycopg2([], [], reject_writes=True)
        _patch_sql_query(fake_mod, monkeypatch)
        res = await sql_mod.sql_query({"query": "DELETE FROM data.t"})
        assert "error" in res
        assert "read-only" in res["error"]

    async def test_missing_query_returns_error(self):
        res = await tool_registry["sql_query"]({"no_query": True})
        assert "error" in res


# ---------------------------------------------------------------------------
# web_search
# ---------------------------------------------------------------------------
class TestWebSearch:
    @pytest.fixture
    def cache_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("WEB_SEARCH_CACHE_DIR", str(tmp_path / "wsc"))
        return tmp_path / "wsc"

    def _fake_tavily(self, call_count):
        async def fake_post(self, url, json=None, headers=None):
            call_count["n"] += 1
            return SimpleNamespace(
                status_code=200,
                raise_for_status=lambda: None,
                json=lambda: {"results": [
                    {"title": "T1", "url": "https://a", "content": "s1"},
                    {"title": "T2", "url": "https://b", "content": "s2"},
                ]},
            )
        return fake_post

    async def test_no_api_key_returns_error(self, monkeypatch, cache_dir):
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        res = await tool_registry["web_search"]({"query": "ethiopia inflation"})
        assert "TAVILY_API_KEY" in res["error"]

    async def test_success_and_cache_hit(self, monkeypatch, cache_dir):
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
        call_count = {"n": 0}

        with patch("packages.tools.web_search.httpx.AsyncClient") as fake_client:
            client = fake_client.return_value.__aenter__.return_value
            client.post = self._fake_tavily(call_count)

            first = await tool_registry["web_search"]({"query": "ethiopia inflation", "max_results": 2})
            assert first["cached"] is False
            assert len(first["results"]) == 2
            assert first["results"][0]["title"] == "T1"

            second = await tool_registry["web_search"]({"query": "ethiopia inflation", "max_results": 2})
            assert second["cached"] is True
            assert call_count["n"] == 1  # second call served from cache

    async def test_cache_respects_ttl(self, monkeypatch, cache_dir):
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
        monkeypatch.setenv("WEB_SEARCH_CACHE_TTL", "1")
        call_count = {"n": 0}

        with patch("packages.tools.web_search.httpx.AsyncClient") as fake_client:
            client = fake_client.return_value.__aenter__.return_value
            client.post = self._fake_tavily(call_count)
            await tool_registry["web_search"]({"query": "x", "max_results": 1})

        # Force the cache entry to be older than the TTL
        cache_files = list(cache_dir.glob("*.json"))
        assert len(cache_files) == 1
        rec = json.loads(cache_files[0].read_text())
        rec["ts"] = time.time() - 9999
        cache_files[0].write_text(json.dumps(rec))

        with patch("packages.tools.web_search.httpx.AsyncClient") as fake_client:
            client = fake_client.return_value.__aenter__.return_value
            client.post = self._fake_tavily(call_count)
            res = await tool_registry["web_search"]({"query": "x", "max_results": 1})
        assert res["cached"] is False
        assert call_count["n"] == 2  # stale cache missed, hit the API again

    async def test_api_error_is_surfaced(self, monkeypatch, cache_dir):
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")

        with patch("packages.tools.web_search.httpx.AsyncClient") as fake_client:
            client = fake_client.return_value.__aenter__.return_value

            async def fake_post(self, url, json=None, headers=None):
                raise Exception("boom")

            client.post = fake_post
            res = await tool_registry["web_search"]({"query": "x"})
        assert "request failed" in res["error"]

    async def test_missing_query_returns_error(self, cache_dir):
        res = await tool_registry["web_search"]({"no_query": True})
        assert "error" in res
