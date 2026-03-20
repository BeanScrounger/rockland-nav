"""
Approval server for The Rockland Navigator.

Serves a browser-based approval UI showing the formatted HTML newsletter.
The editor clicks Approve or Reject; the server captures the decision,
shuts itself down, and returns the result to the caller.
"""

import logging
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Shared state (set by handler, read by main)
# ─────────────────────────────────────────────
_decision: dict = {"value": None}  # "approved" | "rejected" | None
_shutdown_event = threading.Event()


# ─────────────────────────────────────────────
# HTML for the approval page
# ─────────────────────────────────────────────

def _build_approval_page(newsletter_html: str) -> str:
    """Wrap the newsletter preview in an approval UI."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Rockland Navigator — Approval</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #f0f0ec;
    }}

    /* ── Sticky toolbar ── */
    #toolbar {{
      position: fixed;
      top: 0; left: 0; right: 0;
      z-index: 1000;
      background: #1a4a2e;
      color: white;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 24px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }}
    #toolbar h1 {{
      font-size: 16px;
      font-weight: 600;
      letter-spacing: 0.3px;
    }}
    #toolbar .subtitle {{
      font-size: 12px;
      opacity: 0.7;
      margin-top: 2px;
    }}
    .btn-group {{ display: flex; gap: 12px; align-items: center; }}

    .btn {{
      display: inline-block;
      padding: 10px 24px;
      border: none;
      border-radius: 6px;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      transition: opacity 0.15s, transform 0.1s;
    }}
    .btn:hover {{ opacity: 0.88; transform: translateY(-1px); }}
    .btn:active {{ transform: translateY(0); }}
    .btn-approve {{
      background: #4caf50;
      color: white;
    }}
    .btn-reject {{
      background: #e53935;
      color: white;
    }}

    /* ── Preview wrapper ── */
    #preview-wrapper {{
      margin-top: 70px;   /* offset for fixed toolbar */
      padding: 24px 16px;
    }}

    /* ── Result overlay ── */
    #result-overlay {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.6);
      z-index: 2000;
      align-items: center;
      justify-content: center;
    }}
    #result-overlay.show {{ display: flex; }}
    #result-box {{
      background: white;
      border-radius: 12px;
      padding: 40px 48px;
      text-align: center;
      max-width: 400px;
    }}
    #result-box h2 {{ font-size: 22px; margin-bottom: 12px; }}
    #result-box p {{ color: #555; font-size: 14px; line-height: 1.5; }}
  </style>
</head>
<body>

  <!-- Toolbar -->
  <div id="toolbar">
    <div>
      <h1>The Rockland Navigator — Draft Review</h1>
      <div class="subtitle">Review the newsletter below, then approve or reject.</div>
    </div>
    <div class="btn-group">
      <button class="btn btn-reject" onclick="submitDecision('reject')">
        ✗ &nbsp;Reject
      </button>
      <button class="btn btn-approve" onclick="submitDecision('approve')">
        ✓ &nbsp;Approve &amp; Publish
      </button>
    </div>
  </div>

  <!-- Newsletter preview -->
  <div id="preview-wrapper">
    {newsletter_html}
  </div>

  <!-- Result overlay -->
  <div id="result-overlay">
    <div id="result-box">
      <h2 id="result-title"></h2>
      <p id="result-msg"></p>
    </div>
  </div>

  <script>
    function submitDecision(decision) {{
      var overlay = document.getElementById('result-overlay');
      var title   = document.getElementById('result-title');
      var msg     = document.getElementById('result-msg');

      if (decision === 'approve') {{
        title.textContent = '✓ Approved!';
        title.style.color = '#2d7a4f';
        msg.textContent   = 'Publishing to Beehiiv… you can close this window.';
      }} else {{
        title.textContent = '✗ Rejected';
        title.style.color = '#e53935';
        msg.textContent   = 'Add notes to manual_input.txt and re-run main.py.';
      }}
      overlay.classList.add('show');

      // Notify the server
      fetch('/decide?action=' + decision)
        .catch(function() {{ /* server may close before response */ }});
    }}
  </script>

</body>
</html>"""


# ─────────────────────────────────────────────
# HTTP request handler
# ─────────────────────────────────────────────

class _ApprovalHandler(BaseHTTPRequestHandler):
    newsletter_html: str = ""

    def log_message(self, fmt, *args):
        # Suppress default HTTP access log (we use our own logger)
        pass

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            # Serve the approval page
            page = _build_approval_page(self.__class__.newsletter_html)
            self._respond(200, "text/html; charset=utf-8", page.encode("utf-8"))

        elif parsed.path == "/decide":
            # Capture the editor's decision
            params = parse_qs(parsed.query)
            action = params.get("action", [""])[0]

            if action in ("approve", "reject"):
                _decision["value"] = action
                logger.info(f"Editor decision received: {action}")
                self._respond(200, "text/plain", b"OK")
                # Signal shutdown from a daemon thread so this handler can return
                t = threading.Thread(target=_shutdown_event.set, daemon=True)
                t.start()
            else:
                self._respond(400, "text/plain", b"Unknown action")

        else:
            self._respond(404, "text/plain", b"Not found")

    def _respond(self, code: int, content_type: str, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def run_approval_server(newsletter_html: str, port: int = 8765) -> bool:
    """
    Start the approval HTTP server, open a browser, and block until the editor
    clicks Approve or Reject.

    Args:
        newsletter_html: The fully formatted HTML newsletter string.
        port: Local port to bind (default 8765).

    Returns:
        True if the editor approved, False if rejected.
    """
    # Reset shared state
    _decision["value"] = None
    _shutdown_event.clear()

    # Attach the newsletter to the handler class
    _ApprovalHandler.newsletter_html = newsletter_html

    server = HTTPServer(("127.0.0.1", port), _ApprovalHandler)
    server.timeout = 1  # Allow the serve loop to check the shutdown event

    url = f"http://localhost:{port}"
    logger.info(f"Approval server running at {url}")

    # Open the browser after a brief delay (so the server is ready)
    def _open_browser():
        time.sleep(0.8)
        webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()

    print(f"\n{'='*60}")
    print(f"  APPROVAL REQUIRED")
    print(f"  Open your browser at: {url}")
    print(f"  (It should open automatically)")
    print(f"{'='*60}\n")

    # Serve until the shutdown event is set
    while not _shutdown_event.is_set():
        server.handle_request()

    # Brief pause to let the final response flush
    time.sleep(0.3)
    server.server_close()
    logger.info("Approval server shut down")

    approved = _decision["value"] == "approve"
    return approved
