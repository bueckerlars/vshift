from typing import Any

from vshift import __version__

OPENAPI_TAGS: list[dict[str, Any]] = [
    {
        "name": "health",
        "description": "Liveness checks and dependency status.",
    },
    {
        "name": "jobs",
        "description": "Transcoding job status, lifecycle, and statistics.",
    },
]

API_DESCRIPTION = """
vshift REST API for monitoring the transcoding pipeline.

## Documentation

- **Swagger UI**: interactive API explorer at `/docs`
- **ReDoc**: alternative reference UI at `/redoc`
- **OpenAPI spec**: machine-readable schema at `/openapi.json`
"""

API_TITLE = "vshift"
API_VERSION = __version__
