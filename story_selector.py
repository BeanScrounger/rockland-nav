"""
Story Selector for The Rockland Navigator.

Opens a browser UI showing all scraped stories grouped by source.
The editor can check/uncheck stories before passing them to Claude.
Activated via --select flag on main.py; skipped entirely otherwise.
"""

import json
import logging
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

_selected_stories: list[dict] = []
_shutdown_event = threading.Event()
_decision_made = False


# ─────────────────────────────────────────────
# Source display names
# ─────────────────────────────────────────────

SOURCE_LABELS = {
    "rockland_report": "Rockland Report",
    "rockland_news": "Rockland News",
    "monsey_scoop": "Monsey Scoop",
    "mid_hudson_news": "Mid Hudson News",
    "rockland_times": "Rockland Times",
    "nyack_news": "Nyack News & Views",
    "daily_voice_new_city": "Daily Voice — New City",
    "daily_voice_monsey": "Daily Voice — Monsey",
    "daily_voice_stony_point": "Daily Voice — Stony Point",
    "daily_voice_spring_valley": "Daily Voice — Spring Valley",
    "daily_voice_haverstraw": "Daily Voice — Haverstraw",
    "daily_voice_pearl_river": "Daily Voice — Pearl River",
    "daily_voice_suffern": "Daily Voice — Suffern",
    "daily_voice_nanuet": "Daily Voice — Nanuet",
    "reddit": "Reddit — r/rocklandcounty",
    "lohud": "LoHud",
    "county_gov": "Rockland County Gov",
    "orangetown": "Orangetown",
    "nyack_gov": "Nyack Village",
    "suffern": "Suffern Village",
    "sloatsburg_village": "Sloatsburg Village",
    "west_haverstraw": "West Haverstraw",
    "manual": "Manual Input",
}


def _source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, source.replace("_", " ").title())


# ─────────────────────────────────────────────
# HTML builder
# ─────────────────────────────────────────────

def _build_selector_page(stories: list[dict]) -> str:
    # Group stories by source
    groups: dict[str, list[tuple[int, dict]]] = {}
    for i, story in enumerate(stories):
        src = story.get("source", "unknown")
        groups.setdefault(src, []).append((i, story))

    # Build story cards grouped by source
    sections_html = ""
    for source, items in groups.items():
        label = _source_label(source)
        cards_html = ""
        for idx, story in items:
            title = story.get("title", "Untitled").replace('"', "&quot;")
            url = story.get("url", "")
            summary = story.get("summary", "")[:180].replace("<", "&lt;").replace(">", "&gt;")
            pub = story.get("published", "")
            published = (pub.strftime("%Y-%m-%d %H:%M") if hasattr(pub, "strftime") else str(pub))[:22]
            link_html = (
                f'<a href="{url}" target="_blank" style="color:#2d7a4f;font-size:12px;'
                f'text-decoration:none;">↗ view article</a>' if url else ""
            )
            cards_html += f"""
            <label class="story-card" for="story_{idx}">
              <input type="checkbox" id="story_{idx}" name="story_{idx}"
                     value="{idx}" checked onchange="updateCount()">
              <div class="story-content">
                <div class="story-title">{title}</div>
                {f'<div class="story-summary">{summary}{"…" if len(story.get("summary","")) > 180 else ""}</div>' if summary else ""}
                <div class="story-meta">{published} &nbsp;{link_html}</div>
              </div>
            </label>"""

        sections_html += f"""
        <div class="source-group">
          <div class="source-header">
            <span class="source-name">{label}</span>
            <span class="source-count">{len(items)} stories</span>
            <button type="button" class="toggle-btn"
              onclick="toggleSource(this, '{source}')">Deselect all</button>
          </div>
          <div class="source-stories" data-source="{source}">
            {cards_html}
          </div>
        </div>"""

    total = len(stories)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Rockland Navigator — Select Stories</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f0f0ec; color: #2c2c2c; }}

    /* Toolbar */
    #toolbar {{
      position: fixed; top: 0; left: 0; right: 0; z-index: 100;
      background: #1a4a2e; color: white;
      display: flex; align-items: center; justify-content: space-between;
      padding: 12px 24px; box-shadow: 0 2px 8px rgba(0,0,0,.3);
      gap: 16px;
    }}
    #toolbar h1 {{ font-size: 15px; font-weight: 600; white-space: nowrap; }}
    #toolbar .subtitle {{ font-size: 12px; opacity: .7; margin-top: 2px; }}
    .toolbar-right {{ display: flex; align-items: center; gap: 12px; flex-shrink: 0; }}
    #count-badge {{
      background: rgba(255,255,255,.15); border-radius: 20px;
      padding: 4px 12px; font-size: 13px; white-space: nowrap;
    }}
    .btn {{
      padding: 9px 22px; border: none; border-radius: 6px;
      font-size: 14px; font-weight: 600; cursor: pointer;
      transition: opacity .15s, transform .1s; white-space: nowrap;
    }}
    .btn:hover {{ opacity: .88; transform: translateY(-1px); }}
    .btn-go {{ background: #4caf50; color: white; }}
    .btn-all {{ background: rgba(255,255,255,.2); color: white; font-size: 12px; padding: 6px 14px; }}

    /* Content */
    #content {{ margin-top: 70px; padding: 24px 20px; max-width: 860px; margin-left: auto; margin-right: auto; }}
    #content {{ margin-top: 80px; }}

    .source-group {{
      background: white; border-radius: 8px; margin-bottom: 16px;
      box-shadow: 0 1px 3px rgba(0,0,0,.08); overflow: hidden;
    }}
    .source-header {{
      background: #f7f7f3; border-bottom: 1px solid #e8e8e0;
      padding: 10px 16px; display: flex; align-items: center; gap: 10px;
    }}
    .source-name {{ font-weight: 600; font-size: 14px; flex: 1; }}
    .source-count {{
      font-size: 12px; color: #888; background: #eee;
      border-radius: 10px; padding: 2px 8px;
    }}
    .toggle-btn {{
      font-size: 11px; color: #2d7a4f; background: none; border: 1px solid #2d7a4f;
      border-radius: 4px; padding: 2px 8px; cursor: pointer;
    }}
    .toggle-btn:hover {{ background: #f0faf4; }}

    .story-card {{
      display: flex; align-items: flex-start; gap: 12px;
      padding: 12px 16px; border-bottom: 1px solid #f0f0ec;
      cursor: pointer; transition: background .1s;
    }}
    .story-card:last-child {{ border-bottom: none; }}
    .story-card:hover {{ background: #fafaf7; }}
    .story-card input[type="checkbox"] {{
      margin-top: 3px; flex-shrink: 0; width: 16px; height: 16px;
      accent-color: #2d7a4f; cursor: pointer;
    }}
    .story-card.unchecked {{ opacity: .45; }}
    .story-content {{ flex: 1; min-width: 0; }}
    .story-title {{ font-size: 14px; font-weight: 500; line-height: 1.4; margin-bottom: 4px; }}
    .story-summary {{ font-size: 12px; color: #666; line-height: 1.5; margin-bottom: 4px; }}
    .story-meta {{ font-size: 11px; color: #999; display: flex; gap: 10px; align-items: center; }}

    /* Result overlay */
    #overlay {{
      display: none; position: fixed; inset: 0;
      background: rgba(0,0,0,.55); z-index: 200;
      align-items: center; justify-content: center;
    }}
    #overlay.show {{ display: flex; }}
    #overlay-box {{
      background: white; border-radius: 12px; padding: 36px 44px;
      text-align: center; max-width: 360px;
    }}
    #overlay-box h2 {{ font-size: 20px; color: #1a4a2e; margin-bottom: 10px; }}
    #overlay-box p {{ color: #555; font-size: 14px; line-height: 1.5; }}
  </style>
</head>
<body>

<div id="toolbar">
  <div>
    <h1>The Rockland Navigator — Story Selection</h1>
    <div class="subtitle">Check the stories you want Claude to use. Uncheck anything irrelevant.</div>
  </div>
  <div class="toolbar-right">
    <button class="btn btn-all" onclick="selectAll(true)">Select all</button>
    <button class="btn btn-all" onclick="selectAll(false)">Deselect all</button>
    <div id="count-badge">{total} / {total} selected</div>
    <button class="btn btn-go" onclick="submitSelection()">
      ✓ &nbsp;Continue with selected
    </button>
  </div>
</div>

<div id="content">
  <form id="story-form">
    {sections_html}
  </form>
</div>

<div id="overlay">
  <div id="overlay-box">
    <h2>✓ Got it!</h2>
    <p>Passing your selected stories to Claude…<br>You can close this window.</p>
  </div>
</div>

<script>
  var total = {total};

  function updateCount() {{
    var checked = document.querySelectorAll('input[type="checkbox"]:checked').length;
    document.getElementById('count-badge').textContent = checked + ' / ' + total + ' selected';
    // Dim unchecked cards
    document.querySelectorAll('.story-card').forEach(function(card) {{
      var cb = card.querySelector('input[type="checkbox"]');
      card.classList.toggle('unchecked', !cb.checked);
    }});
  }}

  function selectAll(state) {{
    document.querySelectorAll('input[type="checkbox"]').forEach(function(cb) {{
      cb.checked = state;
    }});
    document.querySelectorAll('.toggle-btn').forEach(function(btn) {{
      btn.textContent = state ? 'Deselect all' : 'Select all';
    }});
    updateCount();
  }}

  function toggleSource(btn, source) {{
    var group = document.querySelector('[data-source="' + source + '"]');
    var boxes = group.querySelectorAll('input[type="checkbox"]');
    var anyChecked = Array.from(boxes).some(function(cb) {{ return cb.checked; }});
    boxes.forEach(function(cb) {{ cb.checked = !anyChecked; }});
    btn.textContent = anyChecked ? 'Select all' : 'Deselect all';
    updateCount();
  }}

  function submitSelection() {{
    var checked = Array.from(
      document.querySelectorAll('input[type="checkbox"]:checked')
    ).map(function(cb) {{ return parseInt(cb.value); }});

    document.getElementById('overlay').classList.add('show');

    fetch('/select', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{selected: checked}})
    }}).catch(function() {{ /* server closes */ }});
  }}

  // Init dim state
  updateCount();
</script>

</body>
</html>"""


# ─────────────────────────────────────────────
# HTTP handler
# ─────────────────────────────────────────────

class _SelectorHandler(BaseHTTPRequestHandler):
    stories: list[dict] = []

    def log_message(self, fmt, *args):
        pass  # Suppress access log

    def do_GET(self):
        if urlparse(self.path).path == "/":
            page = _build_selector_page(self.__class__.stories)
            body = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        global _selected_stories, _decision_made
        if urlparse(self.path).path == "/select":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            indices = data.get("selected", [])

            all_stories = self.__class__.stories
            _selected_stories = [all_stories[i] for i in indices if i < len(all_stories)]
            _decision_made = True

            logger.info(f"Story selection received: {len(_selected_stories)} / {len(all_stories)} stories chosen")

            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")

            threading.Thread(target=_shutdown_event.set, daemon=True).start()
        else:
            self.send_response(404)
            self.end_headers()


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def select_stories(stories: list[dict], port: int = 8764) -> list[dict]:
    """
    Open a browser UI to let the editor choose which scraped stories
    to pass to Claude. Returns the selected subset.

    If called without --select flag (i.e. not called at all), all stories
    pass through automatically — this function is only invoked when the
    editor wants manual control.

    Args:
        stories: Full deduplicated story list.
        port: Local port for the selection server (default 8764,
              one below the approval server on 8765).

    Returns:
        List of editor-selected story dicts.
    """
    global _selected_stories, _decision_made
    _selected_stories = []
    _decision_made = False
    _shutdown_event.clear()

    _SelectorHandler.stories = stories

    server = HTTPServer(("127.0.0.1", port), _SelectorHandler)
    server.timeout = 1

    url = f"http://localhost:{port}"
    logger.info(f"Story selector running at {url}")

    def _open():
        time.sleep(0.6)
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()

    print(f"\n{'='*60}")
    print(f"  STORY SELECTION")
    print(f"  {len(stories)} stories scraped — choose what to include.")
    print(f"  Opening browser at: {url}")
    print(f"{'='*60}\n")

    while not _shutdown_event.is_set():
        server.handle_request()

    time.sleep(0.3)
    server.server_close()
    logger.info(f"Story selector closed — {len(_selected_stories)} stories selected")

    return _selected_stories
