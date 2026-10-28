from .http_fetch import http_fetch
from .code_execution import code_execution
from .sql_query import sql_query
from .web_search import web_search

tool_registry = {
    "http_fetch": http_fetch,
    "code_execution": code_execution,
    "sql_query": sql_query,
    "web_search": web_search,
}
