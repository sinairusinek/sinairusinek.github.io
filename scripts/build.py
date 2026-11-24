#!/usr/bin/env python3
"""Generate index.html listing every public GitHub Pages site for OWNER.

Discovers repos with has_pages via the REST API, probes each site for its
HTTP status and <title>, and renders a static index. Sites served from
private repos are skipped so their URLs stay unlisted.

Env:
  GITHUB_TOKEN  required, needs repo read access
  OWNER         GitHub login (default: sinairusinek)
"""

import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OWNER = os.environ.get("OWNER", "sinairusinek")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = 20

# Link to the full list, including sites served from private repos. This
# opens only for accounts it has been shared with; it is not a public page.
# Pages cannot host such a list itself: every file served from a public
# repo is public, whether or not anything links to it.
FULL_LIST_URL = "https://claude.ai/artifact/Pko8YYqMPVVkBH72WAqJa7"

# Repos to leave out of the public index regardless of what the API reports.
SKIP = {f"{OWNER}.github.io"}  # the index itself

# Hand-written one-liners; repos without an entry fall back to their
# GitHub description, then to nothing.
NOTES = {
    "Hospital-Registers": "Digitization, Datasette site, and Kima settlement matching",
    "GenizaLibraries": "Genizah book lists classed by Friedberg Genizah Project field",
    "pi-ai-tei": "Zigzag presentation",
    "E-GERET": "AI correspondence extractor from BYP",
    "Margins": "ERC application: methods, dashboard, BHB data-model desiderata",
    "HaMeorer": "Digital edition of the historic literary journal",
    "myCeteicean": "CETEIcean TEI rendering experiment",
}


def api(path):
    """GET a paginated API path, returning the concatenated JSON arrays."""
    out = []
    url = f"https://api.github.com{path}"
    while url:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {TOKEN}",
                "User-Agent": "pages-index-generator",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = json.load(r)
            link = r.headers.get("Link", "")
        out.extend(body if isinstance(body, list) else [body])
        m = re.search(r'<([^>]+)>;\s*rel="next"', link)
        url = m.group(1) if m else None
    return out


def probe(url):
    """Return (http_status, page_title). status is 0 if unreachable."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "pages-index-generator"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read(200_000).decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""
    m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I)
    title = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    # Unrendered template placeholders are worse than no title.
    if "${" in title or len(title) > 120:
        title = ""
    return status, title


def collect():
    repos = api("/user/repos?per_page=100&affiliation=owner")
    sites = []
    for r in repos:
        if not r.get("has_pages") or r.get("private") or r["name"] in SKIP:
            continue
        url = f"https://{OWNER}.github.io/{r['name']}/"
        status, title = probe(url)
        sites.append(
            {
                "repo": r["name"],
                "url": url,
                "title": title or r["name"],
                "desc": NOTES.get(r["name"], r.get("description") or ""),
                "pushed": (r.get("pushed_at") or "")[:10],
                "ok": status == 200,
                "status": status,
            }
        )
        print(f"  {r['name']:24} {status or 'unreachable':>4}  {title[:50]}", file=sys.stderr)
    sites.sort(key=lambda s: s["pushed"], reverse=True)
    return sites


def render(sites):
    checked = datetime.now(timezone.utc).strftime("%-d %B %Y")
    live = sum(1 for s in sites if s["ok"])
    broken = [s for s in sites if not s["ok"]]

    rows = []
    for s in sites:
        e = {k: html.escape(str(v)) for k, v in s.items()}
        tag = (
            f'<span class="tag broken">{e["status"] or "unreachable"}</span>'
            if not s["ok"]
            else ""
        )
        desc = f'<span>{e["desc"]}</span>' if s["desc"] else ""
        key = html.escape(f"{s['repo']} {s['title']} {s['desc']}".lower())
        rows.append(
            f'''<li class="card" data-key="{key}" data-ok="{str(s['ok']).lower()}">
    <h2><a href="{e['url']}">{e['title']}</a></h2>
    <span class="date">{e['pushed']}</span>
    <div class="url"><a href="{e['url']}">{e['url']}</a></div>
    <div class="meta">
      <a href="https://github.com/{OWNER}/{e['repo']}">{e['repo']}</a>
      {desc}
      {tag}
    </div>
  </li>'''
        )

    note = ""
    if broken:
        names = ", ".join(f"<strong>{html.escape(b['repo'])}</strong>" for b in broken)
        note = (
            f"<p>{len(broken)} site{'s' if len(broken) > 1 else ''} "
            f"did not answer with 200: {names}.</p>"
        )

    return TEMPLATE.format(
        owner=OWNER,
        rows="\n  ".join(rows),
        checked=checked,
        total=len(sites),
        live=live,
        note=note,
        full_list=FULL_LIST_URL,
    )


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Pages Shelf — {owner}</title>
<meta name="description" content="Every public GitHub Pages site published by {owner}.">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{{
  --bg:#fbfaf7; --surface:#fff; --ink:#1c1b18; --ink-soft:#5f5c54;
  --rule:#e3dfd5; --accent:#8a5a2b; --accent-soft:#f1e7da; --dead:#a33a2a;
  --font-display:"Space Grotesk",Georgia,serif;
  --font-body:"Inter",system-ui,sans-serif;
  --font-mono:"IBM Plex Mono",ui-monospace,monospace;
  color-scheme:light;
}}
@media (prefers-color-scheme:dark){{
  :root{{
    --bg:#171614; --surface:#201e1b; --ink:#f0ece4; --ink-soft:#a39d91;
    --rule:#332f2a; --accent:#d9a46a; --accent-soft:#2c2520; --dead:#e08573;
    color-scheme:dark;
  }}
}}
*{{box-sizing:border-box}}
body{{background:var(--bg);color:var(--ink);font-family:var(--font-body);
  font-size:16px;line-height:1.55;margin:0}}
.wrap{{max-width:52rem;margin:0 auto;
  padding-left:max(16px,env(safe-area-inset-left,0px));
  padding-right:max(16px,env(safe-area-inset-right,0px));
  padding-block:2.5rem 4rem}}
h1{{font-family:var(--font-display);font-size:clamp(1.9rem,5vw,2.6rem);
  font-weight:700;letter-spacing:-.02em;margin:0 0 .4rem;text-wrap:balance}}
header p{{color:var(--ink-soft);margin:0;max-width:42rem}}
.owner{{font-family:var(--font-mono);font-size:.8rem;letter-spacing:.04em;
  text-transform:uppercase;color:var(--accent);margin:0 0 .6rem}}
.bar{{position:sticky;top:0;z-index:5;background:var(--bg);
  border-bottom:1px solid var(--rule);display:flex;flex-wrap:wrap;gap:.5rem;
  align-items:center;padding-block:.75rem;margin-top:2rem}}
.bar input{{flex:1 1 12rem;min-width:0;font:inherit;font-size:.95rem;
  color:var(--ink);background:var(--surface);border:1px solid var(--rule);
  border-radius:6px;padding:.45rem .6rem}}
.bar input:focus-visible,.chip:focus-visible,a:focus-visible{{
  outline:2px solid var(--accent);outline-offset:2px}}
.chip{{font:inherit;font-size:.82rem;font-weight:500;color:var(--ink-soft);
  background:transparent;border:1px solid var(--rule);border-radius:999px;
  padding:.35rem .7rem;cursor:pointer}}
.chip[aria-pressed="true"]{{background:var(--accent-soft);
  border-color:var(--accent);color:var(--accent)}}
.count{{font-family:var(--font-mono);font-size:.78rem;color:var(--ink-soft);
  margin-left:auto;font-variant-numeric:tabular-nums}}
ul.list{{list-style:none;margin:0;padding:0}}
.card{{border-bottom:1px solid var(--rule);padding-block:1.1rem;display:grid;
  grid-template-columns:1fr auto;gap:.2rem 1rem;align-items:baseline}}
.card h2{{font-family:var(--font-display);font-size:1.08rem;font-weight:600;
  margin:0;letter-spacing:-.01em;min-width:0}}
.card h2 a{{color:var(--ink);text-decoration:none;
  border-bottom:1px solid var(--accent)}}
.card h2 a:hover{{color:var(--accent)}}
.meta{{grid-column:1/-1;font-family:var(--font-mono);font-size:.76rem;
  color:var(--ink-soft);display:flex;flex-wrap:wrap;gap:.1rem .8rem;
  align-items:center;min-width:0}}
.meta a{{color:var(--ink-soft)}}
.url{{grid-column:1/-1;font-family:var(--font-mono);font-size:.78rem;
  word-break:break-all;min-width:0}}
.url a{{color:var(--accent);text-decoration:none}}
.url a:hover{{text-decoration:underline}}
.date{{font-family:var(--font-mono);font-size:.78rem;color:var(--ink-soft);
  font-variant-numeric:tabular-nums;white-space:nowrap}}
.tag{{display:inline-block;font-family:var(--font-mono);font-size:.68rem;
  letter-spacing:.05em;text-transform:uppercase;border:1px solid var(--rule);
  border-radius:3px;padding:.05rem .35rem}}
.tag.broken{{color:var(--dead);border-color:var(--dead)}}
.card[hidden]{{display:none!important}}
.empty{{color:var(--ink-soft);padding-block:2rem;font-style:italic}}
footer{{margin-top:2.5rem;padding-top:1.5rem;border-top:1px solid var(--rule);
  color:var(--ink-soft);font-size:.88rem}}
footer a.full{{color:var(--accent);text-decoration:none;
  border-bottom:1px solid var(--accent)}}
footer a.full:hover{{background:var(--accent-soft)}}
footer code{{font-family:var(--font-mono);font-size:.82rem;
  background:var(--surface);border:1px solid var(--rule);border-radius:4px;
  padding:.1rem .3rem;word-break:break-all}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <p class="owner">github.com/{owner}</p>
    <h1>Pages Shelf</h1>
    <p>Every public GitHub Pages site published from this account. GitHub has no
    view that lists these — the repository tab filters by language, type and
    visibility, never by whether Pages is on — so this page is generated weekly
    from the API.</p>
  </header>

  <div class="bar">
    <input id="q" type="search" placeholder="Filter by name or title…" aria-label="Filter sites">
    <button class="chip" id="f-broken" aria-pressed="false">Not responding</button>
    <span class="count" id="count"></span>
  </div>

  <ul class="list" id="list">
  {rows}
  <li class="empty" id="empty" hidden>Nothing matches that filter.</li>
  </ul>

  <footer>
    <p>{live} of {total} sites answered when checked on {checked}.</p>
    {note}
    <p>Sites served from private repositories are deliberately omitted here:
    anything this site serves is public, so listing them would make their URLs
    discoverable. <a class="full" href="{full_list}">The full list, including
    those</a> opens only for accounts it has been shared with.</p>
    <p>To regenerate the complete list yourself, run
    <code>gh api --paginate "/user/repos?per_page=100&amp;affiliation=owner" --jq '.[] | select(.has_pages) | .name'</code>.</p>
  </footer>
</div>
<script>
var list=document.getElementById("list"),q=document.getElementById("q"),
    fb=document.getElementById("f-broken"),count=document.getElementById("count"),
    empty=document.getElementById("empty"),
    cards=[].slice.call(list.querySelectorAll(".card"));
function apply(){{
  var term=q.value.trim().toLowerCase(),
      onlyBroken=fb.getAttribute("aria-pressed")==="true",shown=0;
  cards.forEach(function(c){{
    var hit=(!term||c.dataset.key.indexOf(term)>-1)
      &&(!onlyBroken||c.dataset.ok==="false");
    c.hidden=!hit; if(hit)shown++;
  }});
  empty.hidden=shown>0;
  count.textContent=shown+" of "+cards.length+" sites";
}}
q.addEventListener("input",apply);
fb.addEventListener("click",function(){{
  fb.setAttribute("aria-pressed",fb.getAttribute("aria-pressed")==="true"?"false":"true");
  apply();
}});
apply();
</script>
</body>
</html>
"""


def main():
    if not TOKEN:
        sys.exit("GITHUB_TOKEN is not set")
    print(f"Discovering Pages sites for {OWNER}…", file=sys.stderr)
    sites = collect()
    if not sites:
        sys.exit("No public Pages sites found — refusing to write an empty index")
    (ROOT / "index.html").write_text(render(sites), encoding="utf-8")
    print(f"Wrote index.html with {len(sites)} sites", file=sys.stderr)


if __name__ == "__main__":
    main()
