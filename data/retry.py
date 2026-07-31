from __future__ import annotations

import time
import logging
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

def retry(max_retries: int = 3, delay_seconds: float = 1.0) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: Optional[Exception] = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # pragma: no cover - defensive
                    last_error = exc
                    if attempt == max_retries:
                        raise
                    logger.warning("Retry %s/%s for %s failed with %s", attempt, max_retries, func.__name__, exc)
                    time.sleep(delay_seconds * attempt)
            raise last_error  # type: ignore[misc]

        return wrapper

    return decorator
