import datetime
from typing import Any

from ninja import Router

health_router = Router()


@health_router.get("/health", tags=["System"])
def health_check(request: Any) -> dict[str, str]:
    """
    Health check API
    ```
    Args:
        request (Any): request object

    Returns:
        dict[str, str]: health check response
        - status: ok
        - timestamp: current timestamp
    ```
    """
    return {
        "status": "ok",
        "timestamp": datetime.datetime.now().isoformat(),
    }
