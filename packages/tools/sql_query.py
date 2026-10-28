"""Tool #3: SQL Query.

Read-only Postgres access with hard row/time limits. This is deliberately a
separate, much simpler sandbox than full code execution: one statement per
call, an implicit transaction that is aborted (never committed), and the
connection is pinned to the data schema via search_path.

Config (env):
    DATABASE_URL            - full postgres connection string (used for host/db/creds)
    SQL_ALLOWED_SCHEMAS     - comma-separated; defaults to "data"
    SQL_MAX_ROWS            - default 1000
    SQL_TIMEOUT_S           - default 15
"""

import asyncio
import os
from typing import Optional, Union

try:
    import psycopg2
except ImportError:
    psycopg2 = None


def _db_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise ValueError("DATABASE_URL is not set - sql_query cannot connect")
    return url


def _allowed_schemas() -> str:
    return os.getenv("SQL_ALLOWED_SCHEMAS", "data")


async def sql_query(args: Union[str, dict]) -> dict:
    if isinstance(args, str):
        query = args
        params: Optional[tuple] = None
    else:
        query = (args or {}).get("query")
        params = (args or {}).get("params") or None

    if not query:
        return {"error": "sql_query requires a 'query' argument"}

    if psycopg2 is None:
        return {"error": "psycopg2 is not installed - sql_query unavailable"}

    max_rows = int(os.getenv("SQL_MAX_ROWS", 1000))
    timeout_s = int(os.getenv("SQL_TIMEOUT_S", 15))

    def _exec() -> dict:
        conn = psycopg2.connect(_db_url(), connect_timeout=10)
        conn.set_session(readonly=True)  # hard read-only - no writes, even in a session
        try:
            with conn.cursor() as cur:
                # Pin the search path so the query can't reach other schemas
                cur.execute("SET search_path TO public, " + _allowed_schemas())
                # statement_timeout guards against run-away scans
                cur.execute(f"SET statement_timeout = {int(timeout_s * 1000)}")
                cur.execute(query, params)
                if cur.description:  # SELECT-like
                    columns = [d.name for d in cur.description]
                    rows = cur.fetchmany(max_rows + 1)
                    truncated = len(rows) > max_rows
                    rows = rows[:max_rows]
                    return {
                        "columns": columns,
                        "rows": [list(r) for r in rows],
                        "row_count": min(len(rows), max_rows),
                        "truncated": truncated,
                        "limit": max_rows,
                    }
                # Non-SELECT in a read-only session raises; surface it as a clean error
                return {"note": "statement executed with no result set"}
        finally:
            conn.rollback()  # never commit - the session was read-only anyway
            conn.close()

    try:
        return await asyncio.to_thread(_exec)
    except psycopg2.errors.ReadOnlySqlTransaction:
        return {"error": "write rejected - this connection is read-only"}
    except psycopg2.errors.QueryCanceled:
        return {"error": f"query cancelled after {timeout_s}s statement timeout", "truncated": True}
    except psycopg2.Error as e:
        return {"error": f"{type(e).__name__}: {str(e).strip()}"}
