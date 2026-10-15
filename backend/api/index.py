"""Vercel serverless entrypoint.

Vercel's Python runtime serves the ASGI app exported as `app` from this file.

NOTE ON SUITABILITY: this backend was designed for a long-running process.
On serverless it runs with real constraints:

  * SSE streaming is subject to the function's execution limit, so a long
    model turn can be cut off mid-stream.
  * The SQLAlchemy pool cannot persist across invocations, so each cold start
    opens new connections. Use a POOLED Neon connection string.
  * The in-process rate limiter keeps per-instance counters, so limits are
    effectively much weaker than configured.

For a deployment that needs reliable streaming, run `backend/Dockerfile` or
`backend/render.yaml` on a container host instead.
"""
from app.main import app

__all__ = ["app"]
