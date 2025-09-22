import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        rid = request_id_ctx.get()
        record.request_id = rid or "-"
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        base: Dict[str, Any] = {
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "time": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False)


def init_logging(debug: bool = False) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    level = logging.DEBUG if debug else logging.INFO
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)


async def request_context_middleware(request, call_next):  # type: ignore
    rid = str(uuid.uuid4())
    token = request_id_ctx.set(rid)
    logger = logging.getLogger("app.request")
    logger.debug("request start")
    try:
        response = await call_next(request)
        return response
    finally:
        logger.debug("request end")
        request_id_ctx.reset(token)
