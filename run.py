"""Production entrypoint for the local-host dashboard web service.

Runs under waitress rather than Flask's built-in dev server: every request
does blocking subprocess I/O (systemctl/journalctl calls across 30+ units),
and Flask's dev server is documented as unfit for anything beyond trivial
single-request local testing.
"""
from waitress import serve

from lh_dashboard.web import create_app

app = create_app()

if __name__ == "__main__":
    serve(app, host="127.0.0.1", port=8099)
