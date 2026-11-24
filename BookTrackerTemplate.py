import json

from BookTrackerVer import APP_NAME, VERSION


def _safe_json_for_script(obj) -> str:
    """json.dumps(), but safe to embed inside a <script> tag.

    Plain json.dumps() does not escape '<', so a book title/author/etc.
    containing the literal text "</script>" -- typed by a user, or
    returned by an external metadata source we don't control -- would
    prematurely close the surrounding <script> tag when the browser's
    HTML parser runs (which happens before any JS parsing), letting an
    attacker inject arbitrary HTML/script into the page. Escaping '<',
    '>', and '&' as \\uXXXX sequences neutralizes that while remaining
    valid JSON and decoding back to the exact original string in JS."""
    return (json.dumps(obj)
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026"))

MONTH_NAMES = {1: 'January', 2: 'February', 3: 'March', 4: 'April',
               5: 'May', 6: 'June', 7: 'July', 8: 'August',
               9: 'September', 10: 'October', 11: 'November', 12: 'December'}

THEME_CSS = """
:root {
    --bg:#0d0d1a; --surface:#141425; --surface2:#1a1a32; --surface3:#1c1c34;
    --border:#28284a; --border2:#333358;
    --text:#e4e4f0; --text-dim:#8888aa;
    --accent:#818cf8; --accent2:#c084fc;
    --row-odd:#131324; --row-hover:#1c1c38; --row-star:#16223f;
    --menu-bg:#1c1c34; --menu-border:#3a3a66; --menu-row-hover:#272746;
    --toggle-outer1:#3c3c5c; --toggle-outer2:#08080f;
    --toggle-inner1:#44445e; --toggle-inner2:#111120;
    --toggle-icon:#6c8cff; --toggle-glow:rgba(108,140,255,.6);
    --toggle-ring:rgba(255,255,255,.08); --toggle-shadow:rgba(0,0,0,.6);
    --star-empty-fill:#2a2a42; --star-empty-stroke:#6a6a90;
    --star-fill-on:#5b8dff; --star-stroke-on:#3b6fed; --star-glow-on:rgba(91,141,255,.6);
    --status-toread:#7a7a9a; --status-reading:#e0a83e; --status-read1:#5b8dff; --status-read2:#3b6fed;
    --status-dropped:#e0616a; --status-empty-bg:#232342; --status-empty-border:#3a3a5e;
    --badge-ebook-bg:#1a2a4a; --badge-ebook-border:#3a5a8a; --badge-ebook-text:#8ab8ff;
    --badge-print-bg:#2a2a1a; --badge-print-border:#6a6a3a; --badge-print-text:#d8d8a0;
    --badge-audio-bg:#2a1a3a; --badge-audio-border:#6a3a7a; --badge-audio-text:#d8a0f0;
    --shadow-lg:0 20px 60px rgba(0,0,0,.7);
}
[data-theme="light"] {
    --bg:#eef0f7; --surface:#ffffff; --surface2:#f4f5fb; --surface3:#eef0f9;
    --border:#e2e4f0; --border2:#d3d6ea;
    --text:#23233a; --text-dim:#77778f;
    --accent:#6a5acd; --accent2:#a855f7;
    --row-odd:#f7f8fc; --row-hover:#eceefa; --row-star:#e8f0ff;
    --menu-bg:#ffffff; --menu-border:#dcdce8; --menu-row-hover:#f4f5fb;
    --toggle-outer1:#ffffff; --toggle-outer2:#c9cbdb;
    --toggle-inner1:#fbfbfe; --toggle-inner2:#d7d9e6;
    --toggle-icon:#9497a8; --toggle-glow:rgba(0,0,0,0);
    --toggle-ring:rgba(0,0,0,0); --toggle-shadow:rgba(0,0,0,.3);
    --star-empty-fill:#eef0f7; --star-empty-stroke:#9a9ab0;
    --star-fill-on:#3b6fed; --star-stroke-on:#2749b0; --star-glow-on:rgba(59,111,237,.35);
    --status-toread:#9494a8; --status-reading:#c98a1e; --status-read1:#5b8dff; --status-read2:#2749b0;
    --status-dropped:#d14550; --status-empty-bg:#f1f2f9; --status-empty-border:#dadce8;
    --badge-ebook-bg:#e7f0ff; --badge-ebook-border:#a9c6f5; --badge-ebook-text:#2f5fa8;
    --badge-print-bg:#f5f2e2; --badge-print-border:#cbc190; --badge-print-text:#8a7a2a;
    --badge-audio-bg:#f3e7fb; --badge-audio-border:#d3aeee; --badge-audio-text:#8a3aad;
    --shadow-lg:0 16px 44px rgba(30,30,60,.12);
}
"""

BASE_CSS = THEME_CSS + """
* { margin:0; padding:0; box-sizing:border-box; }
body {
    background:var(--bg); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
    padding:2rem 1.5rem; color:var(--text); min-height:100vh; display:flex; justify-content:center;
    transition:background 250ms ease, color 250ms ease;
}
.container { max-width:1400px; width:100%; background:var(--surface); border-radius:24px; padding:2rem; box-shadow:var(--shadow-lg); border:1px solid var(--border); transition:background 250ms ease, border-color 250ms ease; }
.header { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; margin-bottom:1.5rem; gap:1rem; }
.header h1 { font-size:1.8rem; font-weight:600; background:linear-gradient(135deg,var(--accent2),var(--accent)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
.header-left { display:flex; align-items:center; gap:.8rem; }
.header-icon { width:2.6rem; height:2.6rem; border-radius:50%; object-fit:cover; box-shadow:0 2px 8px rgba(0,0,0,.3); flex-shrink:0; }
.header-right { display:flex; align-items:center; gap:.8rem; }

/* ---- Buttons: soft 3D / tactile look ---- */
.nav-link {
    color:var(--text); text-decoration:none; font-size:.85rem; white-space:nowrap;
    background:var(--surface2); border:1px solid var(--border2); border-radius:40px; padding:.45rem 1.1rem;
    box-shadow:0 2px 6px rgba(0,0,0,.15), inset 0 1px 0 rgba(255,255,255,.06);
    transition:transform 120ms ease, box-shadow 120ms ease, background 150ms ease;
}
.nav-link:hover { background:var(--menu-row-hover); transform:translateY(-1px); box-shadow:0 4px 10px rgba(0,0,0,.2), inset 0 1px 0 rgba(255,255,255,.08); }
.nav-link:active { transform:translateY(0); box-shadow:inset 0 2px 4px rgba(0,0,0,.25); }

.filter-pill {
    background:var(--surface2); border:1px solid var(--border2); color:var(--text-dim);
    border-radius:40px; padding:.45rem 1.1rem; font-size:.8rem; cursor:pointer; white-space:nowrap;
    box-shadow:0 2px 6px rgba(0,0,0,.15), inset 0 1px 0 rgba(255,255,255,.06);
    transition:transform 120ms ease, box-shadow 120ms ease, background 150ms ease, color 150ms ease;
}
.filter-pill:hover { transform:translateY(-1px); }
.filter-pill:active { transform:translateY(0); box-shadow:inset 0 2px 4px rgba(0,0,0,.25); }
.filter-pill.active { background:linear-gradient(135deg, var(--accent2), var(--accent)); border-color:transparent; color:#fff; box-shadow:0 3px 10px rgba(129,140,248,.4); }

/* ---- Theme toggle: recreated 3D power button ---- */
.theme-toggle {
    --size:2.6rem; width:var(--size); height:var(--size); border-radius:50%; border:none; cursor:pointer;
    position:relative; padding:0; flex-shrink:0;
    background:radial-gradient(circle at 50% 40%, var(--toggle-outer1), var(--toggle-outer2));
    box-shadow:0 6px 16px var(--toggle-shadow), 0 0 0 1px var(--toggle-ring),
        inset 0 1px 1px rgba(255,255,255,.28), inset 0 -2px 3px rgba(0,0,0,.4);
    transition:background 250ms ease, box-shadow 250ms ease;
}
.theme-toggle .ring {
    position:absolute; inset:14%; border-radius:50%;
    background:radial-gradient(circle at 50% 45%, var(--toggle-inner1), var(--toggle-inner2));
    box-shadow:inset 0 2px 4px rgba(0,0,0,.55), inset 0 -1px 1px rgba(255,255,255,.16);
    display:flex; align-items:center; justify-content:center; transition:background 250ms ease;
}
.theme-toggle svg { width:44%; height:44%; }
.theme-toggle svg path, .theme-toggle svg line {
    stroke:var(--toggle-icon); fill:none; stroke-width:2; stroke-linecap:round;
    filter:drop-shadow(0 0 4px var(--toggle-glow));
    transition:stroke 250ms ease, filter 250ms ease;
}
.theme-toggle:active .ring { box-shadow:inset 0 3px 6px rgba(0,0,0,.6); }

/* ---- Custom animated dropdown (replaces native <select>) ---- */
.dd { position:relative; display:inline-flex; align-items:center; gap:.55rem; }
.dd-label { color:var(--text); font-size:.85rem; min-width:5.5rem; }
.dd-btn {
    width:1.6rem; height:1.6rem; border-radius:50%; border:none; cursor:pointer; position:relative; flex-shrink:0;
    background:var(--surface3); box-shadow:0 1px 3px rgba(0,0,0,.25), inset 0 1px 0 rgba(255,255,255,.08);
}
.dd-btn:after {
    content:''; position:absolute; left:50%; top:50%;
    width:0; height:0; border-left:4px solid transparent; border-right:4px solid transparent;
    border-top:5px solid var(--text-dim); transform:translate(-50%,-30%); transition:transform 220ms ease;
}
.dd.open .dd-btn:after { transform:translate(-50%,-30%) rotate(180deg); }
.dd-menu { position:absolute; top:calc(100% + 10px); left:0; z-index:60; pointer-events:none; }
.dd-menu svg { position:absolute; top:0; left:0; overflow:visible; }
.dd-menu .border-fill { fill:var(--menu-bg); fill-opacity:0; transition:fill-opacity 300ms 50ms cubic-bezier(.4,0,.2,1); }
.dd-menu .border-line { fill:none; stroke:var(--menu-border); transition:stroke-dashoffset 320ms cubic-bezier(.4,0,.2,1); }
.dd.open .dd-menu { pointer-events:auto; }
.dd.open .dd-menu .border-fill { fill-opacity:1; }
.dd-rows { position:relative; padding:6px 0; opacity:0; transition:opacity 220ms 50ms ease; overflow-y:auto; }
.dd.open .dd-rows { opacity:1; }
.dd-row { padding:.5rem .9rem; font-size:.85rem; cursor:pointer; color:var(--text); white-space:nowrap; }
.dd-row:hover { background:var(--menu-row-hover); }
.dd-row.selected { color:var(--accent); font-weight:600; }

.nav-bar { display:flex; flex-wrap:wrap; align-items:center; gap:1.2rem; background:var(--surface2); padding:.7rem 1.5rem; border-radius:20px; margin-bottom:1.2rem; border:1px solid var(--border); transition:background 250ms ease, border-color 250ms ease; }
.search-wrap { position:relative; flex:1; min-width:220px; }
#searchInput, #starredSearch { width:100%; background:var(--bg); color:var(--text); border:1px solid var(--border2); border-radius:40px; padding:.5rem 1rem; font-size:.85rem; transition:background 250ms ease, color 250ms ease, border-color 250ms ease; }
#searchInput:focus, #starredSearch:focus { outline:1px solid var(--accent); }
#searchResults { position:absolute; top:110%; left:0; right:0; background:var(--menu-bg); border:1px solid var(--menu-border); border-radius:12px; max-height:420px; overflow-y:auto; z-index:50; display:none; box-shadow:var(--shadow-lg); }
#searchResults .result { padding:.55rem .8rem; border-bottom:1px solid var(--border); cursor:pointer; font-size:.82rem; display:flex; align-items:center; gap:.6rem; }
#searchResults .result:last-child { border-bottom:none; }
#searchResults .result:hover, #searchResults .result.kb-active { background:var(--menu-row-hover); }
#searchResults .result .r-text { flex:1; min-width:0; }
#searchResults .result .r-year { color:var(--text-dim); font-size:.75rem; white-space:nowrap; }
#searchResults .result .r-star { flex-shrink:0; }
#searchResults .hint { padding:.4rem .8rem; font-size:.7rem; color:var(--text-dim); border-bottom:1px solid var(--border); }
.month-selector { display:flex; align-items:center; gap:.6rem; }
.month-selector .step-btn {
    background:var(--surface3); border:1px solid var(--border2); color:var(--text-dim); border-radius:50%;
    width:1.9rem; height:1.9rem; cursor:pointer; box-shadow:0 1px 3px rgba(0,0,0,.2);
}
.month-selector .step-btn:active { box-shadow:inset 0 2px 4px rgba(0,0,0,.25); }
.filter-bar { display:flex; align-items:center; gap:.7rem; margin-bottom:1.2rem; flex-wrap:wrap; }
table { width:100%; border-collapse:collapse; }
th, td { vertical-align:top; }
th { text-align:left; font-size:.72rem; text-transform:uppercase; letter-spacing:.5px; color:var(--text-dim); padding:.65rem .8rem; border-bottom:1px solid var(--border); cursor:pointer; user-select:none; white-space:nowrap; }
td { padding:.65rem .8rem; font-size:.85rem; border-bottom:1px solid var(--border); line-height:1.35; }
tbody tr:nth-child(odd) td { background:var(--row-odd); }
tr:hover td { background:var(--row-hover) !important; }
tr.starred-row td { background:var(--row-star) !important; }
tr.starred-row td:first-child { box-shadow:inset 3px 0 0 var(--star-fill-on); }
tr.flash-highlight td { animation:flashRow 1.8s ease-out; }
.accordion-block.flash-highlight .accordion-header { animation:flashRow 1.8s ease-out; }
@keyframes flashRow { 0% { background:var(--accent) !important; opacity:.35; } 100% { background:inherit; } }
.col-star { width:2.4rem; text-align:center; }
.col-date { white-space:nowrap; width:1%; color:var(--text); font-variant-numeric:tabular-nums; }
.col-vol { white-space:nowrap; width:1%; text-align:center; }
.col-publisher { white-space:nowrap; width:1%; color:var(--text-dim); }
.col-title { min-width:200px; }
.col-author { white-space:nowrap; color:var(--text-dim); }
.editable-title { cursor:pointer; border-bottom:1px dashed var(--border2); }
.editable-title:hover { color:var(--accent); border-bottom-color:var(--accent); }
.starred-title-link { color:inherit; text-decoration:none; cursor:pointer; border-bottom:1px dashed var(--border2); }
.starred-title-link:hover { color:var(--accent); border-bottom-color:var(--accent); }
.col-format { min-width:130px; }
.star-btn, .r-star { background:none; border:none; cursor:pointer; padding:0; line-height:1; display:inline-flex; }
.star-btn svg, .r-star svg { width:1.15rem; height:1.15rem; }
.star-btn svg path, .r-star svg path {
    fill:var(--star-empty-fill); stroke:var(--star-empty-stroke); stroke-width:1.6;
    transition:fill 150ms ease, stroke 150ms ease, filter 150ms ease;
}
.star-btn.on svg path, .r-star.on svg path {
    fill:var(--star-fill-on); stroke:var(--star-stroke-on);
    filter:drop-shadow(0 0 3px var(--star-glow-on));
}
a.volume-link { color:var(--accent); text-decoration:none; }
a.volume-link:hover { text-decoration:underline; }
.format-badge { display:inline-block; padding:.2rem .8rem; border-radius:40px; font-size:.68rem; font-weight:600; text-transform:uppercase; background:var(--surface3); border:1px solid var(--border2); color:var(--text-dim); margin:0 .3rem .3rem 0; }
.format-badge.ebook { background:var(--badge-ebook-bg); border-color:var(--badge-ebook-border); color:var(--badge-ebook-text); }
.format-badge.print { background:var(--badge-print-bg); border-color:var(--badge-print-border); color:var(--badge-print-text); }
.format-badge.audiobook { background:var(--badge-audio-bg); border-color:var(--badge-audio-border); color:var(--badge-audio-text); }
.empty-state { text-align:center; padding:3rem 1rem; color:var(--text-dim); font-size:.9rem; }

/* ---- Status picker: 4-way segmented control (To-Read/Reading/Read/Dropped) ---- */
.status-picker { display:inline-flex; gap:.3rem; align-items:center; }
.status-btn {
    width:1.7rem; height:1.7rem; border-radius:50%; border:1.5px solid var(--status-empty-border);
    background:var(--status-empty-bg); cursor:pointer; display:flex; align-items:center; justify-content:center;
    padding:0; flex-shrink:0; transition:transform 120ms ease, border-color 150ms ease, background 150ms ease;
}
.status-btn:hover { transform:translateY(-1px); }
.status-btn svg { width:60%; height:60%; }
.status-btn svg path, .status-btn svg line { stroke-width:2.4; stroke-linecap:round; stroke-linejoin:round; fill:none; }
.status-btn[data-status="to_read"] svg path { stroke:var(--status-toread); }
.status-btn[data-status="reading"] svg path { stroke:var(--status-reading); }
.status-btn[data-status="read"] svg path { stroke:var(--status-read1); }
.status-btn[data-status="dropped"] svg path { stroke:var(--status-dropped); }
.status-btn.active[data-status="to_read"] { background:color-mix(in srgb, var(--status-toread) 18%, var(--status-empty-bg)); border-color:var(--status-toread); }
.status-btn.active[data-status="reading"] { background:color-mix(in srgb, var(--status-reading) 22%, var(--status-empty-bg)); border-color:var(--status-reading); }
.status-btn.active[data-status="read"] { background:linear-gradient(135deg, var(--status-read1), var(--status-read2)); border-color:var(--status-read2); box-shadow:0 0 0 1px var(--status-read2), 0 2px 6px rgba(59,111,237,.4); }
.status-btn.active[data-status="read"] svg path { stroke:#fff; }
.status-btn.active[data-status="dropped"] { background:color-mix(in srgb, var(--status-dropped) 22%, var(--status-empty-bg)); border-color:var(--status-dropped); }
.status-badge { display:inline-flex; align-items:center; gap:.3rem; font-size:.72rem; padding:.15rem .6rem; border-radius:40px; border:1px solid var(--border2); color:var(--text-dim); white-space:nowrap; }

/* ---- Accordion (series list on Starred page / status-filtered view) ---- */
.accordion-block { margin-bottom:.9rem; border:1px solid var(--border); border-radius:14px; overflow:hidden; }
.accordion-header { background:var(--surface2); padding:.7rem 1rem; display:flex; align-items:center; gap:.8rem; cursor:pointer; user-select:none; }
.accordion-header:hover { background:var(--menu-row-hover); }
.accordion-chevron { width:0.7rem; height:0.7rem; border-right:2px solid var(--text-dim); border-bottom:2px solid var(--text-dim); transform:rotate(-45deg); transition:transform 200ms ease; flex-shrink:0; }
.accordion-block.expanded .accordion-chevron { transform:rotate(45deg); }
.accordion-title { font-size:.95rem; font-weight:600; flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.accordion-count { font-size:.72rem; color:var(--text-dim); white-space:nowrap; }
.accordion-body { max-height:0; overflow:hidden; transition:max-height 280ms cubic-bezier(.4,0,.2,1); }
.accordion-block.expanded .accordion-body { max-height:2000px; }
.accordion-unstar { background:none; border:1px solid var(--border2); color:var(--text); border-radius:40px; padding:.25rem .7rem; font-size:.7rem; cursor:pointer; white-space:nowrap; }
.accordion-unstar:hover { background:var(--menu-row-hover); }
.col-status { white-space:nowrap; width:1%; }
.col-edit { white-space:nowrap; width:1%; }
.edit-row-btn { background:var(--surface2); border:1px solid var(--border2); color:var(--text-dim); border-radius:8px; width:1.9rem; height:1.9rem; cursor:pointer; font-size:.85rem; line-height:1; }
.edit-row-btn:hover { color:var(--text); border-color:var(--accent); }
.format-tracker { display:inline-flex; gap:.2rem; align-items:center; padding:.15rem .3rem; border-radius:40px; background:var(--surface3); border:1px solid var(--border2); }
.fmt-track-btn { background:none; border:none; cursor:pointer; font-size:.85rem; padding:.15rem .3rem; border-radius:40px; opacity:.35; filter:grayscale(1); transition:opacity 150ms ease, filter 150ms ease, background 150ms ease; }
.fmt-track-btn:hover { opacity:.7; }
.fmt-track-btn.active { opacity:1; filter:none; background:var(--menu-row-hover); }

@media (max-width: 640px) {
    body { padding:.85rem .5rem; }
    .container { padding:1rem; border-radius:16px; }
    .header { gap:.6rem; }
    .header h1 { font-size:1.3rem; }
    .header-icon { width:2rem; height:2rem; }
    .header-left, .header-right { flex-wrap:wrap; row-gap:.5rem; }

    .nav-bar { flex-direction:column; align-items:stretch; padding:.7rem 1rem; }
    .month-selector { justify-content:space-between; }
    .search-wrap { min-width:0; }

    .filter-bar { gap:.5rem; }
    .filter-pill { padding:.35rem .8rem; font-size:.75rem; }

    table, thead, tbody, tr, td { display:block; width:100%; }
    thead { display:none; }
    tbody tr {
        border:1px solid var(--border); border-radius:12px; padding:.6rem .8rem; margin-bottom:.6rem;
        background:var(--row-odd);
    }
    tbody tr:hover td { background:transparent !important; }
    tr.starred-row { background:var(--row-star); }
    tr.starred-row td:first-child { box-shadow:none; }
    td { border-bottom:none !important; padding:.25rem 0 !important; display:flex; align-items:center; justify-content:space-between; gap:.6rem; }
    td[data-label]::before {
        content:attr(data-label); font-size:.68rem; font-weight:600; text-transform:uppercase;
        letter-spacing:.4px; color:var(--text-dim); flex-shrink:0;
    }
    td.no-label { padding:0 !important; }
    td.no-label::before { content:none; }
    .col-star { justify-content:flex-start !important; order:-2; }
    .col-title { order:-1; font-size:1rem; font-weight:600; white-space:normal; }
    .col-title::before { content:none; }
    .col-format { flex-wrap:wrap; justify-content:flex-end; }

    .accordion-header { flex-wrap:wrap; }
    .accordion-title { flex-basis:100%; white-space:normal; }
    .accordion-count { order:1; }

    .dd-menu { max-width:calc(100vw - 3rem); }
}
"""

THEME_INIT_SCRIPT = """
(function() {
    var saved = localStorage.getItem('booktracker-theme');
    if (saved === 'light' || saved === 'dark') {
        document.documentElement.setAttribute('data-theme', saved);
    }
})();
"""

THEME_TOGGLE_HTML = """
<button class="theme-toggle" id="themeToggle" title="Toggle light/dark theme">
    <span class="ring">
        <svg viewBox="0 0 24 24">
            <path d="M12 2v6"/>
            <path d="M18.4 6.6a8 8 0 1 1-12.8 0"/>
        </svg>
    </span>
</button>
"""

THEME_TOGGLE_JS = """
document.getElementById('themeToggle').addEventListener('click', () => {
    const html = document.documentElement;
    const cur = html.getAttribute('data-theme') || 'dark';
    const next = cur === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    localStorage.setItem('booktracker-theme', next);
});
"""

DROPDOWN_JS = """
function buildDropdown(root, options, selected, onSelect) {
    const menu = root.querySelector('.dd-menu');
    const label = root.querySelector('.dd-label');
    const rowH = 34;
    const width = Math.max(140, root.dataset.width ? parseInt(root.dataset.width) : 160);
    const maxHeight = 240;
    const contentHeight = options.length * rowH + 12;
    const height = Math.min(contentHeight, maxHeight);
    const r = 10;
    const perim = 2 * (width + height) - 8 * r + 2 * Math.PI * r;

    menu.innerHTML = `
        <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
            <rect class="border-fill" x="1" y="1" width="${width-2}" height="${height-2}" rx="${r}"
                stroke-dasharray="${perim}" stroke-dashoffset="${perim}"></rect>
            <rect class="border-line" x="1" y="1" width="${width-2}" height="${height-2}" rx="${r}"
                stroke-dasharray="${perim}" stroke-dashoffset="${perim}"></rect>
        </svg>
        <div class="dd-rows" style="width:${width}px; max-height:${height}px;"></div>
    `;
    const rowsEl = menu.querySelector('.dd-rows');
    let selectedRow = null;
    options.forEach(opt => {
        const row = document.createElement('div');
        row.className = 'dd-row' + (opt.value == selected ? ' selected' : '');
        row.textContent = opt.label;
        if (opt.value == selected) { selectedRow = row; label.textContent = opt.label; }
        row.addEventListener('click', (e) => {
            e.stopPropagation();
            label.textContent = opt.label;
            rowsEl.querySelectorAll('.dd-row').forEach(r => r.classList.remove('selected'));
            row.classList.add('selected');
            closeDropdown(root);
            onSelect(opt.value);
        });
        rowsEl.appendChild(row);
    });

    function openDropdown() {
        document.querySelectorAll('.dd.open').forEach(d => { if (d !== root) closeDropdown(d); });
        root.classList.add('open');
        const fill = menu.querySelector('.border-fill');
        const line = menu.querySelector('.border-line');
        requestAnimationFrame(() => {
            fill.style.strokeDashoffset = '0';
            line.style.strokeDashoffset = '0';
        });
        if (selectedRow) selectedRow.scrollIntoView({block: 'nearest'});
    }
    root._closeDropdown = function() {
        root.classList.remove('open');
        const fill = menu.querySelector('.border-fill');
        const line = menu.querySelector('.border-line');
        if (fill) fill.style.strokeDashoffset = perim;
        if (line) line.style.strokeDashoffset = perim;
    };

    root.querySelector('.dd-btn').onclick = (e) => {
        e.stopPropagation();
        if (root.classList.contains('open')) closeDropdown(root); else openDropdown();
    };
}
function closeDropdown(root) { if (root._closeDropdown) root._closeDropdown(); }
document.addEventListener('click', () => {
    document.querySelectorAll('.dd.open').forEach(d => closeDropdown(d));
});
"""

STAR_ICON_JS = """
const STAR_SVG = '<svg viewBox="0 0 24 24"><path d="M12 2.5l2.9 6.26 6.6.87-4.86 4.55 1.28 6.7L12 17.6l-5.92 3.28 1.28-6.7L2.5 9.63l6.6-.87z"/></svg>';
"""

STATUS_JS = """
const STATUS_LABELS = {to_read: 'To-Read', reading: 'Reading', read: 'Read', dropped: 'Dropped'};
const STATUS_ORDER = ['to_read', 'reading', 'read', 'dropped'];
const STATUS_ICONS = {
    to_read: '<svg viewBox="0 0 24 24"><path d="M12 2.5l2.9 6.26 6.6.87-4.86 4.55 1.28 6.7L12 17.6l-5.92 3.28 1.28-6.7L2.5 9.63l6.6-.87z"/></svg>',
    reading: '<svg viewBox="0 0 24 24"><path d="M4 12.5l5 5L20 7"/></svg>',
    read: '<svg viewBox="0 0 24 24"><path d="M1.5 12.5l4.5 4.5L15.5 7.5"/><path d="M8.5 12.5l4.5 4.5L22.5 7.5"/></svg>',
    dropped: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>'
};

function statusPickerHTML(kind, key, current) {
    const fn = kind === 'series' ? 'setSeriesStatus' : 'setVolumeStatus';
    return '<span class="status-picker">' + STATUS_ORDER.map(s => `
        <button class="status-btn ${s === current ? 'active' : ''}" data-status="${s}"
            title="${STATUS_LABELS[s]}"
            onclick="event.stopPropagation(); ${fn}('${key}', '${s}', this)">${STATUS_ICONS[s]}</button>
    `).join('') + '</span>';
}

function markPickerActive(pickerEl, status) {
    pickerEl.querySelectorAll('.status-btn').forEach(b => b.classList.toggle('active', b.dataset.status === status));
}

async function setVolumeStatus(releaseId, status, btnEl) {
    const resp = await fetch('/api/volume_status', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({release_id: parseInt(releaseId), status})
    });
    const data = await resp.json();
    applyStatusChanges(data.changed);
}

async function setSeriesStatus(slug, status, btnEl) {
    const resp = await fetch('/api/series_status', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({slug, status})
    });
    const data = await resp.json();
    applyStatusChanges(data.changed);
}
"""

ACCORDION_JS = """
function toggleAccordion(headerEl) {
    const block = headerEl.parentElement;
    const wasExpanded = block.classList.contains('expanded');
    block.parentElement.querySelectorAll('.accordion-block.expanded').forEach(b => b.classList.remove('expanded'));
    if (!wasExpanded) block.classList.add('expanded');
}

function volNum(v) {
    const n = parseFloat(v);
    return isNaN(n) ? Infinity : n;
}

const FORMAT_TRACK_ICONS = {
    ebook: '🖥️', print: '📖', audiobook: '🔊'
};

function formatTrackerHTML(slug, tracked) {
    return '<span class="format-tracker" title="Track to completion...">' +
        Object.keys(FORMAT_TRACK_ICONS).map(fmt => `
            <button class="fmt-track-btn ${tracked.includes(fmt) ? 'active' : ''}" data-fmt="${fmt}"
                title="Track ${fmt}"
                onclick="event.stopPropagation(); toggleFormatTrack('${slug}', '${fmt}', this)">${FORMAT_TRACK_ICONS[fmt]}</button>
        `).join('') + '</span>';
}

async function toggleFormatTrack(slug, fmt, btnEl) {
    const picker = btnEl.closest('.format-tracker');
    const current = Array.from(picker.querySelectorAll('.fmt-track-btn.active')).map(b => b.dataset.fmt);
    const next = current.includes(fmt) ? current.filter(f => f !== fmt) : current.concat([fmt]);
    const resp = await fetch('/api/series_format_pref', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({slug, formats: next})
    });
    const data = await resp.json();
    applyFormatPrefChange(slug, data.formats);
}

function renderAccordion(containerEl, releases, opts) {
    opts = opts || {};
    const expandedSlugs = new Set(
        Array.from(containerEl.querySelectorAll('.accordion-block.expanded')).map(el => el.dataset.slug)
    );

    const grouped = {};
    for (const r of releases) { (grouped[r.slug] = grouped[r.slug] || []).push(r); }
    const bySlug = {};
    for (const slug of Object.keys(grouped)) {
        bySlug[slug] = grouped[slug].sort((a, b) => {
            const va = volNum(a.volume), vb = volNum(b.volume);
            if (va !== vb) return va - vb;
            return a.date < b.date ? -1 : a.date > b.date ? 1 : 0;
        });
    }
    const slugs = Object.keys(bySlug).sort((a, b) => {
        const ta = bySlug[a][0].title, tb = bySlug[b][0].title;
        return ta < tb ? -1 : ta > tb ? 1 : 0;
    });

    if (!slugs.length) {
        containerEl.innerHTML = `<div class="empty-state">${opts.emptyText || 'Nothing here yet.'}</div>`;
        return;
    }

    let html = '';
    for (const slug of slugs) {
        const allVols = bySlug[slug];
        const tracked = allVols[0].format_pref || [];
        const vols = tracked.length
            ? allVols.filter(r => tracked.some(f => r[f]))
            : allVols;
        const seriesLabel = allVols[0].series_title || allVols[0].title;
        const title = escapeHtml(seriesLabel) + (allVols[0].author ? ` <span style="color:var(--text-dim);font-weight:400;font-size:.85em;">— ${escapeHtml(allVols[0].author)}</span>` : '');
        const seriesStatus = vols.length && vols.every(v => v.status === vols[0].status) ? vols[0].status : null;
        const expandedCls = expandedSlugs.has(slug) ? ' expanded' : '';
        const countLabel = tracked.length && vols.length !== allVols.length
            ? `${vols.length} of ${allVols.length} vols`
            : `${allVols.length} vol${allVols.length > 1 ? 's' : ''}`;
        html += `<div class="accordion-block${expandedCls}" data-slug="${slug}">
            <div class="accordion-header" onclick="toggleAccordion(this)">
                <span class="accordion-chevron"></span>
                <span class="accordion-title">${title}</span>
                <span class="accordion-count">${countLabel}</span>
                ${formatTrackerHTML(slug, tracked)}
                ${statusPickerHTML('series', slug, seriesStatus)}
                ${opts.showUnstar ? `<button class="accordion-unstar" onclick="event.stopPropagation(); unstarFromAccordion('${slug}')">Unstar</button>` : ''}
            </div>
            <div class="accordion-body">
                <table>
                    <thead><tr>
                        <th class="col-date">Date</th>
                        <th class="col-vol">Vol</th>
                        <th class="col-title">Title</th>
                        <th class="col-author">Author</th>
                        <th class="col-publisher">Publisher</th>
                        <th class="col-format">Format</th>
                        <th class="col-status">Status</th>
                        <th class="col-edit"></th>
                    </tr></thead>
                    <tbody>`;
        for (const r of vols) {
            let badges = '';
            if (r.ebook) badges += `<span class="format-badge ebook">Ebook</span>`;
            if (r.print) badges += `<span class="format-badge print">Print</span>`;
            if (r.audiobook) badges += `<span class="format-badge audiobook">Audiobook</span>`;
            const titleText = r.title || seriesLabel;
            const isStandaloneManual = r.source === 'manual' && !allVols[0].series_title;
            const volText = isStandaloneManual ? '' : (r.volume || '');
            html += `<tr data-release-id="${r.id}">
                <td class="col-date" data-label="Date">${escapeHtml(r.date)}</td>
                <td class="col-vol" data-label="Vol"><a class="volume-link" href="${escapeAttr(r.url || '#')}" target="_blank" rel="noopener noreferrer">${escapeHtml(volText)}</a></td>
                <td class="col-title" data-label="Title">${r.source === 'manual' ? `<span class="editable-title" onclick="event.stopPropagation(); openEditModal(${r.id})" title="Click to view/edit">${escapeHtml(titleText)}</span>` : escapeHtml(titleText)}</td>
                <td class="col-author" data-label="Author">${escapeHtml(r.author || '')}</td>
                <td class="col-publisher" data-label="Publisher">${escapeHtml(r.publisher || '')}</td>
                <td class="col-format" data-label="Format">${badges}</td>
                <td class="col-status" data-label="Status">${statusPickerHTML('volume', r.id, r.status || 'to_read')}</td>
                <td class="col-edit" data-label=""><button class="edit-row-btn" title="Edit this book" onclick="event.stopPropagation(); openEditModal(${r.id})">✎</button></td>
            </tr>`;
        }
        html += `</tbody></table></div></div>`;
    }
    containerEl.innerHTML = html;
}
"""


BOOK_FIELDS_CSS = """
.field-grid { display:grid; grid-template-columns:repeat(3, 1fr); gap:1rem 1.2rem; }
.field-grid .field-wide { grid-column:1 / -1; }
.field-grid label { display:block; font-size:.72rem; letter-spacing:.03em; text-transform:uppercase; color:var(--text-dim); margin-bottom:.35rem; }
.field-grid input, .field-grid textarea, .field-grid select {
    width:100%; background:var(--bg); color:var(--text); border:1px solid var(--border2); border-radius:10px;
    padding:.55rem .7rem; font-size:.85rem; font-family:inherit; transition:border-color 150ms ease;
}
.field-grid input:focus, .field-grid textarea:focus, .field-grid select:focus { outline:none; border-color:var(--accent); }
.field-grid textarea { resize:vertical; min-height:4.5rem; }
@media (max-width:820px) { .field-grid { grid-template-columns:repeat(2, 1fr); } }
@media (max-width:560px) { .field-grid { grid-template-columns:1fr; } }

.format-toggle-group { display:flex; gap:.7rem; flex-wrap:wrap; }
.format-toggle {
    background:var(--surface2); border:1px solid var(--border2); color:var(--text-dim);
    border-radius:40px; padding:.5rem 1.1rem; font-size:.82rem; cursor:pointer; font-family:inherit;
    display:flex; align-items:center; gap:.4rem; transition:background 150ms ease, color 150ms ease, border-color 150ms ease;
}
.format-toggle.active { background:linear-gradient(135deg,var(--accent2),var(--accent)); border-color:transparent; color:#fff; }

.version-tag { font-size:.68rem; color:var(--text-dim); align-self:center; white-space:nowrap; }

.modal-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,.55); z-index:100; align-items:flex-start; justify-content:center; padding:4vh 1rem; overflow-y:auto; }
.modal-overlay.open { display:flex; }
.modal-box { background:var(--surface); border:1px solid var(--border); border-radius:18px; box-shadow:var(--shadow-lg); width:100%; max-width:720px; max-height:92vh; display:flex; flex-direction:column; overflow:hidden; }
.modal-header { display:flex; align-items:center; justify-content:space-between; padding:1.1rem 1.3rem; border-bottom:1px solid var(--border); user-select:none; }
.modal-header h2 { font-size:1.1rem; font-weight:600; }
.modal-close { background:none; border:none; color:var(--text-dim); font-size:1.4rem; cursor:pointer; line-height:1; padding:.2rem .4rem; }
.modal-close:hover { color:var(--text); }
.modal-body { padding:1.1rem 1.3rem; overflow-y:auto; flex:1; }
.modal-footer { display:flex; justify-content:space-between; align-items:center; gap:.6rem; padding:1rem 1.3rem; border-top:1px solid var(--border); }
.modal-btn { border:none; border-radius:40px; padding:.55rem 1.2rem; font-size:.82rem; cursor:pointer; white-space:nowrap; font-family:inherit; }
.modal-btn.primary { background:linear-gradient(135deg,var(--accent2),var(--accent)); color:#fff; box-shadow:0 3px 10px rgba(129,140,248,.4); }
.modal-btn.primary:disabled { opacity:.5; cursor:default; }
.modal-btn.secondary { background:var(--surface2); border:1px solid var(--border2); color:var(--text); }
.modal-btn.danger { background:none; border:1px solid var(--status-dropped); color:var(--status-dropped); }
.edit-research-row { display:grid; grid-template-columns:140px 1fr 160px auto; gap:.6rem; margin-bottom:.9rem; padding-bottom:1rem; border-bottom:1px solid var(--border); }
.edit-research-row select, .edit-research-row input { background:var(--bg); color:var(--text); border:1px solid var(--border2); border-radius:10px; padding:.5rem .7rem; font-size:.82rem; font-family:inherit; }
@media (max-width:560px) { .edit-research-row { grid-template-columns:1fr 1fr; } .edit-research-row button { grid-column:1 / -1; } }
"""
BASE_CSS = BASE_CSS + BOOK_FIELDS_CSS

BOOK_FIELDS_JS = """
const BOOK_FIELD_DEFS = [
    {key: 'title', label: 'Title / Album', wide: false},
    {key: 'subtitle', label: 'Subtitle', wide: false},
    {key: 'author', label: 'Author', wide: false},
    {key: 'narrator', label: 'Narrator', wide: false},
    {key: 'series_title', label: 'Series', wide: false},
    {key: 'volume', label: 'Series Volume', wide: false},
    {key: 'publisher', label: 'Publisher', wide: false},
    {key: 'language', label: 'Language', wide: false},
    {key: 'runtime_minutes', label: 'Runtime (minutes)', wide: false, type: 'number'},
    {key: 'isbn', label: 'ISBN', wide: false},
    {key: 'cover_url', label: 'Cover URL', wide: false},
    {key: 'date', label: 'Release Date', wide: false, type: 'date'},
    {key: 'genres', label: 'Genres', wide: false},
    {key: 'source_label', label: 'Source', wide: false},
    {key: 'url', label: 'Source URL', wide: true},
    {key: 'description', label: 'Summary / Description', wide: true, type: 'textarea'},
];

function bookFieldsHTML(prefix, v) {
    v = v || {};
    return '<div class="field-grid">' + BOOK_FIELD_DEFS.map(f => {
        const id = prefix + f.key;
        const val = (v[f.key] === undefined || v[f.key] === null) ? '' : v[f.key];
        const cls = f.wide ? 'field-wide' : '';
        let control;
        if (f.type === 'textarea') {
            control = `<textarea id="${id}">${escapeHtml(String(val))}</textarea>`;
        } else {
            control = `<input id="${id}" type="${f.type || 'text'}" value="${escapeAttr(String(val))}">`;
        }
        return `<div class="${cls}"><label>${f.label}</label>${control}</div>`;
    }).join('') + '</div>';
}

function collectBookFields(prefix) {
    const out = {};
    for (const f of BOOK_FIELD_DEFS) {
        const el = document.getElementById(prefix + f.key);
        if (!el) continue;
        let val = el.value.trim();
        if (f.key === 'runtime_minutes') { out[f.key] = val ? parseInt(val) : null; }
        else { out[f.key] = val || null; }
    }
    return out;
}

function formatToggleGroupHTML(prefix, active) {
    active = active || [];
    const opts = [['ebook', '🖥️ Ebook'], ['print', '📖 Print'], ['audiobook', '🔊 Audiobook']];
    return '<div class="format-toggle-group" id="' + prefix + 'fmtGroup">' + opts.map(([key, label]) => `
        <button type="button" class="format-toggle ${active.includes(key) ? 'active' : ''}" data-fmt="${key}"
            onclick="this.classList.toggle('active')">${label}</button>
    `).join('') + '</div>';
}

function collectFormatToggles(prefix) {
    const group = document.getElementById(prefix + 'fmtGroup');
    if (!group) return [];
    return Array.from(group.querySelectorAll('.format-toggle.active')).map(b => b.dataset.fmt);
}

function detailToFormValues(d) {
    return Object.assign({}, d, {volume: (d.series_volume !== undefined && d.series_volume !== null) ? d.series_volume : (d.volume || '')});
}

function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c]));
}
function escapeAttr(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}
"""

EDIT_MODAL_HTML = """
<div class="modal-overlay" id="editModalOverlay" onclick="if (event.target === this) closeEditModal()">
  <div class="modal-box">
    <div class="modal-header">
      <h2>✎ Edit Book</h2>
      <button class="modal-close" onclick="closeEditModal()">&times;</button>
    </div>
    <div class="modal-body" id="editModalBody">
      <div class="edit-research-row">
          <select id="ef_provider">
              <option value="hardcover">Hardcover</option>
              <option value="openlibrary">Open Library</option>
              <option value="audible">Audible</option>
          </select>
          <input id="ef_query" type="text" placeholder="Re-search by title..." autocomplete="off">
          <input id="ef_author" type="text" placeholder="Author (optional)" autocomplete="off">
          <button class="modal-btn secondary" onclick="runEditModalSearch()">Search</button>
      </div>
      <div class="search-results-list" id="editSearchResultsList"></div>
      <div id="editModalFields"></div>
    </div>
    <div class="modal-footer" id="editModalFooter" style="display:none;"></div>
  </div>
</div>
"""

EDIT_MODAL_JS = """
let editReleaseId = null;
let editSearchResults = [];

async function openEditModal(releaseId) {
    editReleaseId = releaseId;
    const overlay = document.getElementById('editModalOverlay');
    overlay.classList.add('open');
    resetModalPosition(overlay);
    document.getElementById('ef_query').value = '';
    document.getElementById('ef_author').value = '';
    document.getElementById('editSearchResultsList').innerHTML = '';
    editSearchResults = [];
    const fields = document.getElementById('editModalFields');
    fields.innerHTML = '<div class="spinner-row">Loading…</div>';
    document.getElementById('editModalFooter').style.display = 'none';
    let row;
    try {
        const resp = await fetch('/api/release/' + releaseId);
        row = await resp.json();
    } catch (e) {
        fields.innerHTML = '<div class="modal-empty">Could not load this book.</div>';
        return;
    }
    renderEditFields(row);
    const footer = document.getElementById('editModalFooter');
    footer.style.display = 'flex';
    footer.innerHTML = `
        <button class="modal-btn danger" onclick="deleteFromEditModal()">Remove</button>
        <div style="display:flex;gap:.6rem;">
            <button class="modal-btn secondary" onclick="closeEditModal()">Cancel</button>
            <button class="modal-btn primary" id="editSaveBtn" onclick="saveEditModal()">Save changes</button>
        </div>
    `;
}

function renderEditFields(row) {
    const fields = document.getElementById('editModalFields');
    fields.innerHTML = bookFieldsHTML('ef_', row) +
        '<div style="margin-top:1rem;">' + formatToggleGroupHTML('ef_', [
            row.ebook ? 'ebook' : null, row.print ? 'print' : null, row.audiobook ? 'audiobook' : null
        ].filter(Boolean)) + '</div>';
}

function closeEditModal() {
    document.getElementById('editModalOverlay').classList.remove('open');
    editReleaseId = null;
}

async function runEditModalSearch() {
    const provider = document.getElementById('ef_provider').value;
    const q = document.getElementById('ef_query').value.trim();
    const author = document.getElementById('ef_author').value.trim();
    const list = document.getElementById('editSearchResultsList');
    if (q.length < 2) { list.innerHTML = '<div class="modal-empty">Type at least 2 characters.</div>'; return; }
    const kind = provider === 'audible' ? 'audiobook' : 'book';
    list.innerHTML = '<div class="spinner-row">Searching…</div>';
    let results;
    try {
        const params = new URLSearchParams({kind, provider, q, author});
        const resp = await fetch('/api/external_search?' + params.toString());
        const data = await resp.json();
        if (data && data.error) { list.innerHTML = `<div class="modal-empty">${escapeHtml(data.error)}</div>`; return; }
        results = Array.isArray(data) ? data : [];
    } catch (e) { results = []; }
    editSearchResults = results;
    if (!results.length) {
        list.innerHTML = '<div class="modal-empty">No results. Try a different search.</div>';
        return;
    }
    list.innerHTML = results.map((r, i) => `
        <div class="search-result-row" onclick="pickEditModalResult(${i})">
            ${r.cover_url ? `<img class="result-cover" src="${escapeAttr(r.cover_url)}" alt="">` : `<div class="result-cover"></div>`}
            <div class="result-info">
                <div class="result-title">${escapeHtml(r.title)}</div>
                <div class="result-meta">${escapeHtml(r.author || 'Unknown author')}${r.date ? ' • ' + escapeHtml(r.date.slice(0, 4)) : ''}</div>
            </div>
            <span class="result-source">${escapeHtml(r.source)}</span>
        </div>
    `).join('');
}

async function pickEditModalResult(idx) {
    const chosen = editSearchResults[idx];
    if (!chosen) return;
    const provider = document.getElementById('ef_provider').value;
    const kind = provider === 'audible' ? 'audiobook' : 'book';
    const list = document.getElementById('editSearchResultsList');
    list.innerHTML = '<div class="spinner-row">Loading details…</div>';
    let detail;
    try {
        const params = new URLSearchParams({kind, source: chosen.source, external_id: chosen.external_id});
        const resp = await fetch('/api/external_detail?' + params.toString());
        detail = await resp.json();
    } catch (e) {
        detail = chosen;
    }
    renderEditFields(Object.assign({}, detailToFormValues(detail), {
        id: editReleaseId,
        ebook: detail.ebook !== undefined ? detail.ebook : (kind === 'audiobook' ? 0 : 1),
        print: detail.print !== undefined ? detail.print : 0,
        audiobook: detail.audiobook !== undefined ? detail.audiobook : (kind === 'audiobook' ? 1 : 0),
    }));
    list.innerHTML = '';
}

async function saveEditModal() {
    if (!editReleaseId) return;
    const btn = document.getElementById('editSaveBtn');
    btn.disabled = true;
    btn.textContent = 'Saving…';
    const fields = collectBookFields('ef_');
    const formats = collectFormatToggles('ef_');
    fields.ebook = formats.includes('ebook') ? 1 : 0;
    fields.print = formats.includes('print') ? 1 : 0;
    fields.audiobook = formats.includes('audiobook') ? 1 : 0;
    let updated;
    try {
        const resp = await fetch('/api/release/' + editReleaseId + '/update', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(fields)
        });
        updated = await resp.json();
    } catch (e) {
        btn.disabled = false;
        btn.textContent = 'Save changes';
        alert('Could not save — check your connection and try again.');
        return;
    }
    if (typeof onReleaseUpdated === 'function') onReleaseUpdated(updated);
    closeEditModal();
}

async function deleteFromEditModal() {
    if (!editReleaseId) return;
    if (!confirm('Remove this book entirely? This can\\'t be undone.')) return;
    try {
        await fetch('/api/release/' + editReleaseId + '/remove', {method: 'POST'});
    } catch (e) {
        alert('Could not remove — check your connection and try again.');
        return;
    }
    if (typeof onReleaseRemoved === 'function') onReleaseRemoved(editReleaseId);
    closeEditModal();
}

function resetModalPosition(overlay) {
    const box = overlay.querySelector('.modal-box');
    box.style.position = '';
    box.style.left = '';
    box.style.top = '';
    box.style.margin = '';
}

function makeModalDraggable(overlayId) {
    const overlay = document.getElementById(overlayId);
    const box = overlay.querySelector('.modal-box');
    const header = overlay.querySelector('.modal-header');
    let dragging = false, startX = 0, startY = 0, boxStartLeft = 0, boxStartTop = 0;
    const clamp = (v, min, max) => Math.min(Math.max(v, min), max);

    function onDown(e) {
        if (e.target.closest('.modal-close')) return;
        const rect = box.getBoundingClientRect();
        if (box.style.position !== 'fixed') {
            box.style.position = 'fixed';
            box.style.margin = '0';
            box.style.left = rect.left + 'px';
            box.style.top = rect.top + 'px';
        }
        dragging = true;
        boxStartLeft = rect.left;
        boxStartTop = rect.top;
        const p = e.touches ? e.touches[0] : e;
        startX = p.clientX;
        startY = p.clientY;
        header.style.cursor = 'grabbing';
        e.preventDefault();
    }
    function onMove(e) {
        if (!dragging) return;
        const p = e.touches ? e.touches[0] : e;
        const dx = p.clientX - startX;
        const dy = p.clientY - startY;
        const margin = 40;
        const newLeft = clamp(boxStartLeft + dx, margin - box.offsetWidth, window.innerWidth - margin);
        const newTop = clamp(boxStartTop + dy, 0, window.innerHeight - margin);
        box.style.left = newLeft + 'px';
        box.style.top = newTop + 'px';
    }
    function onUp() {
        dragging = false;
        header.style.cursor = 'grab';
    }
    header.style.cursor = 'grab';
    header.addEventListener('mousedown', onDown);
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    header.addEventListener('touchstart', onDown, {passive: false});
    document.addEventListener('touchmove', onMove, {passive: false});
    document.addEventListener('touchend', onUp);
}
makeModalDraggable('editModalOverlay');
"""


def render_year_page(year: int, releases: list, years: list, initial_month: int) -> str:
    year = int(year)
    initial_month = int(initial_month)
    months_present = sorted({int(r['date'][5:7]) for r in releases}) or [initial_month]
    if initial_month not in months_present:
        initial_month = months_present[0]

    data_json = _safe_json_for_script(releases)
    years_json = _safe_json_for_script(years)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{APP_NAME} — Year {year}</title>
<link rel="icon" type="image/png" href="/static/favicon-32.png" sizes="32x32">
<link rel="icon" type="image/png" href="/static/favicon-64.png" sizes="64x64">
<script>{THEME_INIT_SCRIPT}</script>
<style>{BASE_CSS}</style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="header-left">
            <img class="header-icon" src="/static/icon.png" alt="">
            <h1>📚 {APP_NAME} — {year}</h1>
            <span class="version-tag">v{VERSION}</span>
        </div>
        <div class="header-right">
            {THEME_TOGGLE_HTML}
            <a class="nav-link" href="/" title="Jump to current month/year">🏠 Home</a>
            <a class="nav-link" href="/starred">★ My Starred</a>
            <a class="nav-link" href="/my_books">📚 My Books</a>
            <a class="nav-link" href="/add">➕ Add Book</a>
            <div class="dd" id="yearDD" data-width="120">
                <span class="dd-label"></span>
                <button class="dd-btn"></button>
                <div class="dd-menu"></div>
            </div>
        </div>
    </div>

    <div class="nav-bar">
        <div class="month-selector">
            <button class="step-btn" onclick="shiftMonth(-1)">◀</button>
            <div class="dd" id="monthDD" data-width="150">
                <span class="dd-label"></span>
                <button class="dd-btn"></button>
                <div class="dd-menu"></div>
            </div>
            <button class="step-btn" onclick="shiftMonth(1)">▶</button>
        </div>
        <div class="search-wrap">
            <input id="searchInput" type="text" placeholder="Search all years for a title... (Enter to jump, Esc to clear)" autocomplete="off">
            <div id="searchResults"></div>
        </div>
        <span id="countLabel" style="font-size:.8rem;color:var(--text-dim);white-space:nowrap;"></span>
    </div>

    <div class="filter-bar">
        <button class="filter-pill" data-format="ebook">🖥️ Ebook</button>
        <button class="filter-pill" data-format="print">📖 Print</button>
        <button class="filter-pill" data-format="audiobook">🔊 Audiobook</button>
        <button class="filter-pill" id="starredOnlyBtn">★ Starred only</button>
        <div class="dd" id="statusDD" data-width="150">
            <span class="dd-label"></span>
            <button class="dd-btn"></button>
            <div class="dd-menu"></div>
        </div>
    </div>

    <div id="normalView">
        <table>
            <thead>
                <tr>
                    <th class="col-star"></th>
                    <th class="col-date" data-sort="date">Date</th>
                    <th class="col-title" data-sort="title">Title</th>
                    <th class="col-vol" data-sort="volume">Vol</th>
                    <th class="col-publisher" data-sort="publisher">Publisher</th>
                    <th class="col-format">Format</th>
                </tr>
            </thead>
            <tbody id="tableBody"></tbody>
        </table>
    </div>
    <div id="statusView" style="display:none;"></div>
</div>
{EDIT_MODAL_HTML}

<script>
{THEME_TOGGLE_JS}
{DROPDOWN_JS}
{STAR_ICON_JS}
{STATUS_JS}
{ACCORDION_JS}
{BOOK_FIELDS_JS}
{EDIT_MODAL_JS}

function onReleaseUpdated(row) {{
    const idx = releases.findIndex(r => r.id === row.id);
    if (idx >= 0) releases[idx] = row; else releases.push(row);
    render();
}}
function onReleaseRemoved(id) {{
    releases = releases.filter(r => r.id !== id);
    render();
}}

const YEAR = {year};
const YEARS = {years_json};
const MONTHS_PRESENT = {json.dumps(months_present)};
const MONTH_NAMES = {json.dumps(MONTH_NAMES)};
let releases = {data_json};
let currentMonth = {initial_month};
let activeFormats = new Set();
let starredOnly = false;
let sortKey = 'date', sortDir = 1;
let localFilterText = '';
let statusFilter = '';
let statusViewData = [];

buildDropdown(document.getElementById('statusDD'),
    [{{value: '', label: 'All statuses'}}].concat(STATUS_ORDER.map(s => ({{value: s, label: STATUS_LABELS[s]}}))),
    '',
    async (v) => {{
        statusFilter = v;
        const normalView = document.getElementById('normalView');
        const statusView = document.getElementById('statusView');
        if (!v) {{
            normalView.style.display = '';
            statusView.style.display = 'none';
            return;
        }}
        normalView.style.display = 'none';
        statusView.style.display = '';
        statusView.innerHTML = '<div class="empty-state">Loading...</div>';
        const resp = await fetch('/api/by_status/' + v);
        statusViewData = await resp.json();
        renderAccordion(statusView, statusViewData, {{
            showUnstar: false,
            emptyText: `Nothing marked "${{STATUS_LABELS[v]}}" yet. Set statuses from the ★ My Starred page.`
        }});
    }}
);

function applyStatusChanges(changed) {{
    for (const c of changed) {{
        const r = releases.find(x => x.id === c.id);
        if (r) r.status = c.status;
        const r2 = statusViewData.find(x => x.id === c.id);
        if (r2) r2.status = c.status;
    }}
    if (statusFilter) {{
        statusViewData = statusViewData.filter(r => r.status === statusFilter);
        renderAccordion(document.getElementById('statusView'), statusViewData, {{
            showUnstar: false,
            emptyText: `Nothing marked "${{STATUS_LABELS[statusFilter]}}" yet. Set statuses from the ★ My Starred page.`
        }});
    }}
    render();
}}

function applyFormatPrefChange(slug, formats) {{
    releases.forEach(r => {{ if (r.slug === slug) r.format_pref = formats; }});
    statusViewData.forEach(r => {{ if (r.slug === slug) r.format_pref = formats; }});
    if (statusFilter) {{
        renderAccordion(document.getElementById('statusView'), statusViewData, {{
            showUnstar: false,
            emptyText: `Nothing marked "${{STATUS_LABELS[statusFilter]}}" yet. Set statuses from the ★ My Starred page.`
        }});
    }}
}}

buildDropdown(document.getElementById('yearDD'),
    YEARS.map(y => ({{value: y, label: String(y)}})),
    YEAR,
    (v) => {{ location.href = '/year/' + v; }}
);

function rebuildMonthDropdown() {{
    buildDropdown(document.getElementById('monthDD'),
        MONTHS_PRESENT.map(m => ({{value: m, label: MONTH_NAMES[m]}})),
        currentMonth,
        (v) => {{ currentMonth = parseInt(v); render(); }}
    );
}}
rebuildMonthDropdown();

function shiftMonth(delta) {{
    const idx = MONTHS_PRESENT.indexOf(currentMonth);
    const next = idx + delta;
    if (next >= 0 && next < MONTHS_PRESENT.length) {{
        currentMonth = MONTHS_PRESENT[next];
        rebuildMonthDropdown();
        render();
    }}
}}

document.querySelectorAll('.filter-pill[data-format]').forEach(btn => {{
    btn.addEventListener('click', () => {{
        const fmt = btn.dataset.format;
        if (activeFormats.has(fmt)) {{ activeFormats.delete(fmt); btn.classList.remove('active'); }}
        else {{ activeFormats.add(fmt); btn.classList.add('active'); }}
        render();
    }});
}});

document.getElementById('starredOnlyBtn').addEventListener('click', (e) => {{
    starredOnly = !starredOnly;
    e.target.classList.toggle('active', starredOnly);
    render();
}});

document.querySelectorAll('th[data-sort]').forEach(th => {{
    th.addEventListener('click', () => {{
        const key = th.dataset.sort;
        if (sortKey === key) sortDir *= -1; else {{ sortKey = key; sortDir = 1; }}
        render();
    }});
}});

async function toggleStar(slug) {{
    const resp = await fetch('/api/star', {{
        method: 'POST', headers: {{'Content-Type':'application/json'}},
        body: JSON.stringify({{slug}})
    }});
    const data = await resp.json();
    releases.forEach(r => {{ if (r.slug === slug) r.starred = data.starred; }});
    lastSearchResults.forEach(r => {{ if (r.slug === slug) r.starred = data.starred; }});
    render();
    renderSearchResults();
}}

function render() {{
    let filtered = releases.filter(r => parseInt(r.date.slice(5,7)) === currentMonth);
    if (activeFormats.size > 0) {{
        filtered = filtered.filter(r => {{
            for (const fmt of activeFormats) {{ if (r[fmt]) return true; }}
            return false;
        }});
    }}
    if (starredOnly) filtered = filtered.filter(r => r.starred);
    if (localFilterText) {{
        const q = localFilterText.toLowerCase();
        filtered = filtered.filter(r => r.title.toLowerCase().includes(q));
    }}

    filtered.sort((a, b) => {{
        let av = a[sortKey], bv = b[sortKey];
        if (av < bv) return -1 * sortDir;
        if (av > bv) return 1 * sortDir;
        return 0;
    }});

    document.getElementById('countLabel').textContent = filtered.length + ' releases';

    if (!filtered.length) {{
        document.getElementById('tableBody').innerHTML =
            '<tr><td colspan="6" class="empty-state">No releases match the current filters.</td></tr>';
        return;
    }}

    let html = '';
    for (const r of filtered) {{
        let badges = '';
        if (r.ebook) badges += `<span class="format-badge ebook">Ebook</span>`;
        if (r.print) badges += `<span class="format-badge print">Print</span>`;
        if (r.audiobook) badges += `<span class="format-badge audiobook">Audiobook</span>`;
        html += `<tr class="${{r.starred ? 'starred-row' : ''}}" id="row-${{r.id}}">
            <td class="col-star no-label"><button class="star-btn ${{r.starred ? 'on' : ''}}" onclick="toggleStar('${{r.slug}}')">${{STAR_SVG}}</button></td>
            <td class="col-date" data-label="Date">${{escapeHtml(r.date)}}</td>
            <td class="col-title no-label">${{r.starred
                ? `<a class="starred-title-link" href="/starred#series-${{encodeURIComponent(r.slug)}}" title="View this series in ★ My Starred">${{escapeHtml(r.title)}}</a>`
                : escapeHtml(r.title)}}</td>
            <td class="col-vol" data-label="Vol"><a class="volume-link" href="${{escapeAttr(r.url || '#')}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(r.volume || '')}}</a></td>
            <td class="col-publisher" data-label="Publisher">${{escapeHtml(r.publisher || '')}}</td>
            <td class="col-format" data-label="Format">${{badges}}</td>
        </tr>`;
    }}
    document.getElementById('tableBody').innerHTML = html;
}}

let searchTimer = null;
let lastSearchResults = [];
let kbIndex = -1;
const searchInput = document.getElementById('searchInput');
const searchResults = document.getElementById('searchResults');

function renderSearchResults() {{
    if (!lastSearchResults.length) {{
        searchResults.innerHTML = '<div class="result">No matches</div>';
        return;
    }}
    searchResults.innerHTML =
        '<div class="hint">↑↓ to navigate, Enter to open/jump, click ★ to star</div>' +
        lastSearchResults.map((r, i) => `
            <div class="result ${{i === kbIndex ? 'kb-active' : ''}}" data-idx="${{i}}">
                <button class="r-star ${{r.starred ? 'on' : ''}}" onclick="event.stopPropagation(); toggleStar('${{r.slug}}')">${{STAR_SVG}}</button>
                <span class="r-text">${{escapeHtml(r.title)}}${{r.volume ? ' (vol ' + escapeHtml(r.volume) + ')' : ''}} — ${{escapeHtml(r.publisher || '')}}${{r.source === 'manual' ? ' <em style="color:var(--accent);font-style:normal;">✎ edit</em>' : ''}}</span>
                <span class="r-year">${{escapeHtml(r.date)}}</span>
            </div>
        `).join('');
    searchResults.querySelectorAll('.result[data-idx]').forEach(el => {{
        el.addEventListener('click', () => jumpToResult(parseInt(el.dataset.idx)));
    }});
}}

function jumpToResult(idx) {{
    const r = lastSearchResults[idx];
    if (!r) return;
    if (r.source === 'manual') {{
        searchResults.style.display = 'none';
        openEditModal(r.id);
        return;
    }}
    location.href = `/year/${{r.year}}?month=${{parseInt(r.date.slice(5,7))}}#row-${{r.id}}`;
}}

searchInput.addEventListener('input', () => {{
    const q = searchInput.value.trim();
    localFilterText = q;
    render();

    clearTimeout(searchTimer);
    kbIndex = -1;
    if (q.length < 2) {{ searchResults.style.display = 'none'; lastSearchResults = []; return; }}
    searchTimer = setTimeout(async () => {{
        const resp = await fetch('/api/search?q=' + encodeURIComponent(q));
        lastSearchResults = await resp.json();
        renderSearchResults();
        searchResults.style.display = 'block';
    }}, 250);
}});

searchInput.addEventListener('keydown', (e) => {{
    if (e.key === 'Escape') {{
        searchInput.value = '';
        localFilterText = '';
        lastSearchResults = [];
        searchResults.style.display = 'none';
        render();
        return;
    }}
    if (!lastSearchResults.length || searchResults.style.display === 'none') return;
    if (e.key === 'ArrowDown') {{
        e.preventDefault();
        kbIndex = Math.min(kbIndex + 1, lastSearchResults.length - 1);
        renderSearchResults();
    }} else if (e.key === 'ArrowUp') {{
        e.preventDefault();
        kbIndex = Math.max(kbIndex - 1, 0);
        renderSearchResults();
    }} else if (e.key === 'Enter') {{
        e.preventDefault();
        jumpToResult(kbIndex >= 0 ? kbIndex : 0);
    }}
}});

document.addEventListener('click', (e) => {{
    if (!e.target.closest('.search-wrap')) searchResults.style.display = 'none';
}});

(function applyDeepLink() {{
    const params = new URLSearchParams(location.search);
    const monthParam = parseInt(params.get('month'));
    if (monthParam && MONTHS_PRESENT.includes(monthParam)) {{
        currentMonth = monthParam;
        rebuildMonthDropdown();
    }}
    render();
    if (location.hash.startsWith('#row-')) {{
        const el = document.querySelector(location.hash);
        if (el) {{
            el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            el.classList.add('flash-highlight');
        }}
    }}
}})();
</script>
</body>
</html>"""


def render_starred_page(releases: list) -> str:
    data_json = _safe_json_for_script(releases)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{APP_NAME} — My Starred</title>
<link rel="icon" type="image/png" href="/static/favicon-32.png" sizes="32x32">
<link rel="icon" type="image/png" href="/static/favicon-64.png" sizes="64x64">
<script>{THEME_INIT_SCRIPT}</script>
<style>{BASE_CSS}</style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="header-left">
            <img class="header-icon" src="/static/icon.png" alt="">
            <h1>★ My Starred Books</h1>
            <span class="version-tag">v{VERSION}</span>
        </div>
        <div class="header-right">
            {THEME_TOGGLE_HTML}
            <a class="nav-link" href="/" title="Jump to current month/year">🏠 Home</a>
            <a class="nav-link" href="/my_books">📚 My Books</a>
            <a class="nav-link" href="/add">➕ Add Book</a>
        </div>
    </div>

    <div class="nav-bar">
        <div class="search-wrap" style="flex:1;">
            <input id="starredSearch" type="text" placeholder="Filter your starred series by title..." autocomplete="off">
        </div>
        <span id="countLabel" style="font-size:.8rem;color:var(--text-dim);white-space:nowrap;"></span>
    </div>

    <div id="content"></div>
</div>
{EDIT_MODAL_HTML}

<script>
{THEME_TOGGLE_JS}
{STATUS_JS}
{ACCORDION_JS}
{BOOK_FIELDS_JS}
{EDIT_MODAL_JS}

function onReleaseUpdated(row) {{
    const idx = releases.findIndex(r => r.id === row.id);
    if (idx >= 0) releases[idx] = row; else releases.push(row);
    render();
}}
function onReleaseRemoved(id) {{
    releases = releases.filter(r => r.id !== id);
    render();
}}

let releases = {data_json};
let filterText = '';

async function unstarFromAccordion(slug) {{
    await fetch('/api/star', {{
        method: 'POST', headers: {{'Content-Type':'application/json'}},
        body: JSON.stringify({{slug}})
    }});
    releases = releases.filter(r => r.slug !== slug);
    render();
}}

function applyStatusChanges(changed) {{
    const bySlugSeen = new Set();
    for (const c of changed) {{
        const r = releases.find(x => x.id === c.id);
        if (r) r.status = c.status;
    }}
    render();
}}

function applyFormatPrefChange(slug, formats) {{
    releases.forEach(r => {{ if (r.slug === slug) r.format_pref = formats; }});
    render();
}}

function render() {{
    let visible = releases;
    if (filterText) {{
        const q = filterText.toLowerCase();
        const matchingSlugs = new Set(releases.filter(r => r.title.toLowerCase().includes(q)).map(r => r.slug));
        visible = releases.filter(r => matchingSlugs.has(r.slug));
    }}
    document.getElementById('countLabel').textContent =
        new Set(visible.map(r => r.slug)).size + ' series';
    renderAccordion(document.getElementById('content'), visible, {{
        showUnstar: true,
        emptyText: releases.length
            ? 'No starred series match that search.'
            : 'No starred books yet. Star a title from any year page, or from search results, and it will show up here — every volume, automatically.'
    }});
}}

document.getElementById('starredSearch').addEventListener('input', (e) => {{
    filterText = e.target.value.trim();
    render();
}});

render();

(function applyDeepLink() {{
    if (!location.hash.startsWith('#series-')) return;
    const slug = decodeURIComponent(location.hash.slice('#series-'.length));
    const block = document.querySelector('.accordion-block[data-slug="' + CSS.escape(slug) + '"]');
    if (!block) return;
    document.querySelectorAll('.accordion-block.expanded').forEach(b => b.classList.remove('expanded'));
    block.classList.add('expanded');
    block.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    block.classList.add('flash-highlight');
}})();
</script>
</body>
</html>"""


ADD_PAGE_CSS = """
.add-section { background:var(--surface); border:1px solid var(--border); border-radius:16px; padding:1.3rem 1.5rem; margin-bottom:1.2rem; }
.add-section h2 { font-size:.95rem; font-weight:600; margin-bottom:1rem; color:var(--text); }
.add-search-row { display:grid; grid-template-columns:140px 1fr 200px auto; gap:.7rem; margin-bottom:.7rem; align-items:end; }
.add-search-row > div { display:flex; flex-direction:column; }
.add-search-row label { font-size:.68rem; letter-spacing:.03em; text-transform:uppercase; color:var(--text-dim); margin-bottom:.35rem; }
.add-search-row select, .add-search-row input { background:var(--bg); color:var(--text); border:1px solid var(--border2); border-radius:10px; padding:.55rem .7rem; font-size:.85rem; font-family:inherit; }
.add-url-row { display:flex; gap:.7rem; }
.add-url-row input { flex:1; background:var(--bg); color:var(--text); border:1px solid var(--border2); border-radius:10px; padding:.55rem .8rem; font-size:.85rem; font-family:inherit; }
.add-btn { border:none; border-radius:10px; padding:.55rem 1.3rem; font-size:.85rem; cursor:pointer; white-space:nowrap; font-family:inherit; }
.add-btn.primary { background:linear-gradient(135deg,var(--accent2),var(--accent)); color:#fff; box-shadow:0 3px 10px rgba(129,140,248,.4); }
.add-btn.secondary { background:var(--surface2); border:1px solid var(--border2); color:var(--text); }
.add-hint { font-size:.75rem; color:var(--text-dim); margin-top:.3rem; }
.add-warning { font-size:.78rem; color:var(--status-dropped); margin-top:.5rem; }
.search-results-list { margin-top:.8rem; display:flex; flex-direction:column; gap:.3rem; max-height:22rem; overflow-y:auto; }
.search-result-row { display:flex; gap:.8rem; align-items:center; padding:.6rem .5rem; border-radius:10px; cursor:pointer; border:1px solid transparent; }
.search-result-row:hover { background:var(--menu-row-hover); border-color:var(--border2); }
.result-cover { width:2.6rem; height:3.7rem; object-fit:cover; border-radius:4px; background:var(--surface3); flex-shrink:0; }
.result-info { flex:1; min-width:0; }
.result-title { font-size:.88rem; font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.result-meta { font-size:.75rem; color:var(--text-dim); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.result-source { font-size:.65rem; color:var(--text-dim); border:1px solid var(--border2); border-radius:20px; padding:.15rem .55rem; white-space:nowrap; flex-shrink:0; }
.recent-item-row { display:flex; align-items:center; gap:.8rem; padding:.7rem .8rem; border-bottom:1px solid var(--border); }
.recent-item-row:last-child { border-bottom:none; }
.recent-item-row .result-cover { width:2.2rem; height:3.1rem; }
.recent-item-row .result-info { cursor:pointer; }
.recent-item-row .result-info:hover .result-title { color:var(--accent); }
.recent-item-controls { display:flex; align-items:center; gap:.5rem; flex-shrink:0; }
.remove-btn { background:var(--surface2); border:1px solid var(--border2); color:var(--text-dim); border-radius:40px; padding:.4rem 1rem; font-size:.75rem; cursor:pointer; font-family:inherit; }
.remove-btn:hover { color:var(--status-dropped); border-color:var(--status-dropped); }
.spinner-row { text-align:center; padding:1.5rem 0; color:var(--text-dim); font-size:.85rem; }
.modal-empty { text-align:center; color:var(--text-dim); font-size:.85rem; padding:1.5rem 0; }
@media (max-width:820px) {
    .add-search-row { grid-template-columns:1fr 1fr; }
    .add-search-row > div:nth-child(2) { grid-column:1 / -1; }
}
@media (max-width:560px) {
    .add-search-row { grid-template-columns:1fr; }
    .add-url-row { flex-direction:column; }
}

/* ----- My Books page styles ----- */
.import-row { display:flex; gap:.7rem; align-items:center; }
.import-row input[type=file] {
    flex:1; background:var(--bg); color:var(--text); border:1px solid var(--border2);
    border-radius:10px; padding:.55rem .7rem; font-size:.85rem; font-family:inherit;
}
.import-status { margin-top:.7rem; font-size:.85rem; }
.import-status .ok { color:var(--accent); }
.import-status .warn { color:var(--status-reading); }
.import-status .err { color:var(--status-dropped); }
.import-status ul { margin:.4rem 0 0 1.2rem; font-size:.78rem; color:var(--text-dim); }
.section-header { display:flex; align-items:center; gap:.6rem; margin:1.4rem 0 .7rem; font-size:1rem; font-weight:600; }
.section-header .section-count { font-size:.75rem; color:var(--text-dim); font-weight:400; }
.date-read-input {
    background:var(--bg); color:var(--text); border:1px solid var(--border2);
    border-radius:8px; padding:.3rem .5rem; font-size:.82rem; font-family:inherit;
}
.date-read-input:focus { outline:none; border-color:var(--accent); }
.remove-row-btn { background:var(--surface2); border:1px solid var(--border2); color:var(--text-dim); border-radius:40px; padding:.3rem .8rem; font-size:.72rem; cursor:pointer; font-family:inherit; }
.remove-row-btn:hover { color:var(--status-dropped); border-color:var(--status-dropped); }
@media (max-width:640px) {
    .import-row { flex-direction:column; align-items:stretch; }
}
"""
BASE_CSS = BASE_CSS + ADD_PAGE_CSS


def render_add_page(recent: list) -> str:
    recent_json = _safe_json_for_script(recent)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{APP_NAME} — Add a Book</title>
<link rel="icon" type="image/png" href="/static/favicon-32.png" sizes="32x32">
<link rel="icon" type="image/png" href="/static/favicon-64.png" sizes="64x64">
<script>{THEME_INIT_SCRIPT}</script>
<style>{BASE_CSS}</style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="header-left">
            <img class="header-icon" src="/static/icon.png" alt="">
            <h1>➕ Add a Book</h1>
            <span class="version-tag">v{VERSION}</span>
        </div>
        <div class="header-right">
            {THEME_TOGGLE_HTML}
            <a class="nav-link" href="/" title="Jump to current month/year">🏠 Home</a>
            <a class="nav-link" href="/starred">★ My Starred</a>
            <a class="nav-link" href="/my_books">📚 My Books</a>
        </div>
    </div>

    <div class="add-section">
        <h2>🔍 Search your library</h2>
        <div class="search-wrap">
            <input id="searchInput" type="text" placeholder="Find a book you've already added, to view or edit it..." autocomplete="off">
            <div id="searchResults"></div>
        </div>
    </div>

    <div class="add-section">
        <h2>Find a book, ebook, or audiobook</h2>
        <div class="add-search-row">
            <div>
                <label>Provider</label>
                <select id="providerSelect" onchange="onProviderChange()">
                    <option value="hardcover" selected>Hardcover</option>
                    <option value="googlebooks">Google Books</option>
                    <option value="openlibrary">Open Library</option>
                    <option value="audible">Audible</option>
                    <option value="audnexus">Audnexus (ASIN only)</option>
                    <option value="amazon">Amazon (URL only)</option>
                </select>
            </div>
            <div>
                <label id="searchLabel">Search title or ASIN</label>
                <input id="searchQuery" type="text" placeholder="Search title, author, or ASIN..." autocomplete="off">
            </div>
            <div>
                <label>Author (optional)</label>
                <input id="searchAuthor" type="text" placeholder="Author" autocomplete="off">
            </div>
            <button class="add-btn primary" onclick="runAddSearch()" id="searchBtn">Search</button>
        </div>
        <div class="add-url-row">
            <input id="urlInput" type="text" placeholder="...or paste a product URL (e.g. an amazon.com/dp/ or audible.com/pd/ link)">
            <button class="add-btn secondary" onclick="fetchFromUrl()">Fetch from URL</button>
        </div>
        <div id="addHint" class="add-hint"></div>
        <div id="addWarning" class="add-warning" style="display:none;"></div>
        <div class="search-results-list" id="searchResultsList"></div>
    </div>

    <div class="add-section">
        <h2>Details</h2>
        <div id="detailsFields"></div>
        <div style="margin:1.2rem 0;">
            <div class="add-hint" style="margin-bottom:.5rem;">Format:</div>
            <div id="formatToggleContainer"></div>
        </div>
        <div style="display:flex;justify-content:flex-end;">
            <button class="add-btn primary" id="addSubmitBtn" onclick="submitAdd()">+ Add to My Starred</button>
        </div>
    </div>

    <div class="add-section">
        <h2 id="recentHeading">Your {APP_NAME} items (0)</h2>
        <div id="recentList"></div>
    </div>
</div>
{EDIT_MODAL_HTML}

<script>
{THEME_TOGGLE_JS}
{STATUS_JS}
{BOOK_FIELDS_JS}
{EDIT_MODAL_JS}

let recentItems = {recent_json};
let addSource = null;
let addExternalId = null;
let addKind = 'book';

document.getElementById('detailsFields').innerHTML = bookFieldsHTML('f_', {{}});
document.getElementById('formatToggleContainer').innerHTML = formatToggleGroupHTML('f_', ['ebook']);

function onProviderChange() {{
    const provider = document.getElementById('providerSelect').value;
    const label = document.getElementById('searchLabel');
    const query = document.getElementById('searchQuery');
    const author = document.getElementById('searchAuthor');
    const btn = document.getElementById('searchBtn');
    const hint = document.getElementById('addHint');
    if (provider === 'amazon') {{
        label.textContent = 'Search (unavailable)';
        query.disabled = true; author.disabled = true; btn.disabled = true;
        hint.textContent = 'Amazon has no public search API — paste a product URL below instead.';
    }} else if (provider === 'audnexus') {{
        label.textContent = 'ASIN';
        query.disabled = false; author.disabled = true; btn.disabled = false;
        query.placeholder = 'Paste or type an ASIN (e.g. B00BFF369G)...';
        hint.textContent = 'Audnexus only supports exact ASIN lookup, not keyword search.';
    }} else {{
        label.textContent = 'Search title or ASIN';
        query.disabled = false; author.disabled = false; btn.disabled = false;
        query.placeholder = 'Search title, author, or ASIN...';
        hint.textContent = '';
    }}
    if (provider === 'hardcover' && providerStatus && !providerStatus.hardcover_configured) {{
        hint.textContent = 'Hardcover isn\\'t configured yet — add hardcover_token to config.ini (run: python BookTrackerApp.py paths to find it) or set HARDCOVER_API_TOKEN, then restart the app. Free token: hardcover.app/account/api';
    }}
}}

async function runAddSearch() {{
    const provider = document.getElementById('providerSelect').value;
    const q = document.getElementById('searchQuery').value.trim();
    const author = document.getElementById('searchAuthor').value.trim();
    const list = document.getElementById('searchResultsList');
    if (q.length < 2) {{ list.innerHTML = '<div class="modal-empty">Type at least 2 characters.</div>'; return; }}
    const kind = (provider === 'audible' || provider === 'audnexus') ? 'audiobook' : 'book';
    list.innerHTML = '<div class="spinner-row">Searching…</div>';
    let results;
    try {{
        const params = new URLSearchParams({{kind, provider, q, author}});
        const resp = await fetch('/api/external_search?' + params.toString());
        const data = await resp.json();
        if (data && data.error) {{ list.innerHTML = `<div class="modal-empty">${{escapeHtml(data.error)}}</div>`; return; }}
        results = Array.isArray(data) ? data : [];
    }} catch (e) {{ results = []; }}
    if (!results.length) {{
        list.innerHTML = '<div class="modal-empty">No results. Try a different search.</div>';
        return;
    }}
    list.innerHTML = results.map((r, i) => `
        <div class="search-result-row" onclick="pickAddResult(${{i}})">
            ${{r.cover_url ? `<img class="result-cover" src="${{escapeAttr(r.cover_url)}}" alt="">` : `<div class="result-cover"></div>`}}
            <div class="result-info">
                <div class="result-title">${{escapeHtml(r.title)}}</div>
                <div class="result-meta">${{escapeHtml(r.author || 'Unknown author')}}${{r.date ? ' • ' + escapeHtml(r.date.slice(0, 4)) : ''}}</div>
            </div>
            <span class="result-source">${{escapeHtml(r.source)}}</span>
        </div>
    `).join('');
    window._addSearchResults = results;
    window._addSearchKind = kind;
}}

function fillDetailsForm(detail, kind) {{
    addSource = detail.source || null;
    addExternalId = detail.external_id || null;
    addKind = kind;
    document.getElementById('detailsFields').innerHTML = bookFieldsHTML('f_', detailToFormValues(detail));
    const defaultFmt = kind === 'audiobook' ? ['audiobook'] : ['ebook'];
    document.getElementById('formatToggleContainer').innerHTML = formatToggleGroupHTML('f_', defaultFmt);
    document.getElementById('addWarning').style.display = 'none';
}}

async function pickAddResult(idx) {{
    const chosen = (window._addSearchResults || [])[idx];
    if (!chosen) return;
    const kind = window._addSearchKind || 'book';
    if (chosen.narrator !== undefined || chosen.subtitle !== undefined) {{
        fillDetailsForm(chosen, kind);
        return;
    }}
    const list = document.getElementById('searchResultsList');
    list.innerHTML = '<div class="spinner-row">Loading details…</div>';
    try {{
        const params = new URLSearchParams({{kind, source: chosen.source, external_id: chosen.external_id}});
        const resp = await fetch('/api/external_detail?' + params.toString());
        const detail = await resp.json();
        fillDetailsForm(detail, kind);
        list.innerHTML = '';
    }} catch (e) {{
        fillDetailsForm(chosen, kind);
        list.innerHTML = '';
    }}
}}

async function fetchFromUrl() {{
    const url = document.getElementById('urlInput').value.trim();
    if (!url) return;
    const warning = document.getElementById('addWarning');
    warning.style.display = 'none';
    try {{
        const resp = await fetch('/api/external_fetch_url', {{
            method: 'POST', headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{url}})
        }});
        const detail = await resp.json();
        if (detail.error) {{ warning.textContent = detail.error; warning.style.display = 'block'; return; }}
        fillDetailsForm(detail, detail.kind || 'book');
        if (detail.warning) {{ warning.textContent = detail.warning; warning.style.display = 'block'; }}
    }} catch (e) {{
        warning.textContent = 'Could not fetch that URL — check your connection and try again.';
        warning.style.display = 'block';
    }}
}}

async function submitAdd() {{
    const btn = document.getElementById('addSubmitBtn');
    const fields = collectBookFields('f_');
    if (!fields.title) {{ alert('Title is required.'); return; }}
    const formats = collectFormatToggles('f_');
    fields.external_id = addExternalId;
    fields.source = addSource;
    btn.disabled = true;
    btn.textContent = 'Adding…';
    let result;
    try {{
        const resp = await fetch('/api/external_add', {{
            method: 'POST', headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{kind: addKind, formats, volume: fields}})
        }});
        result = await resp.json();
    }} catch (e) {{
        btn.disabled = false; btn.textContent = '+ Add to My Starred';
        alert('Could not add — check your connection and try again.');
        return;
    }}
    btn.disabled = false;
    btn.textContent = '+ Add to My Starred';
    if (result && result.releases && result.releases.length) {{
        const existingIds = new Set(recentItems.map(r => r.id));
        result.releases.forEach(r => {{ if (!existingIds.has(r.id)) recentItems.unshift(r); }});
        renderRecentList();
        document.getElementById('detailsFields').innerHTML = bookFieldsHTML('f_', {{}});
        document.getElementById('searchQuery').value = '';
        document.getElementById('urlInput').value = '';
        document.getElementById('searchResultsList').innerHTML = '';
    }}
}}

function renderRecentList() {{
    document.getElementById('recentHeading').textContent = `Your {APP_NAME} items (${{recentItems.length}})`;
    const list = document.getElementById('recentList');
    if (!recentItems.length) {{
        list.innerHTML = '<div class="modal-empty">Nothing added yet.</div>';
        return;
    }}
    list.innerHTML = recentItems.map(r => `
        <div class="recent-item-row">
            ${{r.cover_url ? `<img class="result-cover" src="${{escapeAttr(r.cover_url)}}" alt="">` : `<div class="result-cover"></div>`}}
            <div class="result-info" onclick="openEditModal(${{r.id}})">
                <div class="result-title">${{escapeHtml(r.title)}}</div>
                <div class="result-meta">${{escapeHtml(r.author || '')}}${{r.series_title ? ' • Series: ' + escapeHtml(r.series_title) + (r.volume ? ' #' + escapeHtml(r.volume) : '') : ''}}</div>
            </div>
            <div class="recent-item-controls">
                ${{statusPickerHTML('volume', r.id, r.status || 'to_read')}}
                <button class="remove-btn" onclick="removeRecentItem(${{r.id}})">Remove</button>
            </div>
        </div>
    `).join('');
}}

async function removeRecentItem(id) {{
    if (!confirm('Remove this book entirely? This can\\'t be undone.')) return;
    try {{
        await fetch('/api/release/' + id + '/remove', {{method: 'POST'}});
    }} catch (e) {{
        alert('Could not remove — check your connection and try again.');
        return;
    }}
    recentItems = recentItems.filter(r => r.id !== id);
    renderRecentList();
}}

function onReleaseUpdated(row) {{
    const idx = recentItems.findIndex(r => r.id === row.id);
    if (idx >= 0) recentItems[idx] = row;
    renderRecentList();
}}
function onReleaseRemoved(id) {{
    recentItems = recentItems.filter(r => r.id !== id);
    renderRecentList();
}}

let providerStatus = null;
async function loadProviderStatus() {{
    try {{
        const resp = await fetch('/api/external_provider_status');
        providerStatus = await resp.json();
    }} catch (e) {{
        providerStatus = null;
    }}
    onProviderChange();
}}

let librarySearchTimer = null;
let libraryResults = [];
let libraryKbIndex = -1;
const librarySearchInput = document.getElementById('searchInput');
const librarySearchResults = document.getElementById('searchResults');

function renderLibraryResults() {{
    if (!libraryResults.length) {{
        librarySearchResults.innerHTML = '<div class="result">No matches</div>';
        return;
    }}
    librarySearchResults.innerHTML =
        '<div class="hint">↑↓ to navigate, Enter to open</div>' +
        libraryResults.map((r, i) => `
            <div class="result ${{i === libraryKbIndex ? 'kb-active' : ''}}" data-idx="${{i}}">
                <span style="width:1.1rem;flex-shrink:0;color:var(--accent);">${{r.starred ? '★' : ''}}</span>
                <span class="r-text">${{escapeHtml(r.title)}}${{r.volume ? ' (vol ' + escapeHtml(r.volume) + ')' : ''}} — ${{escapeHtml(r.publisher || '')}}${{r.source === 'manual' ? ' <em style="color:var(--accent);font-style:normal;">✎ edit</em>' : ''}}</span>
                <span class="r-year">${{escapeHtml(r.date)}}</span>
            </div>
        `).join('');
    librarySearchResults.querySelectorAll('.result[data-idx]').forEach(el => {{
        el.addEventListener('click', () => openLibraryResult(parseInt(el.dataset.idx)));
    }});
}}

function openLibraryResult(idx) {{
    const r = libraryResults[idx];
    if (!r) return;
    librarySearchResults.style.display = 'none';
    if (r.source === 'manual') {{
        openEditModal(r.id);
    }} else {{
        location.href = `/year/${{r.year}}?month=${{parseInt(r.date.slice(5,7))}}#row-${{r.id}}`;
    }}
}}

librarySearchInput.addEventListener('input', () => {{
    const q = librarySearchInput.value.trim();
    clearTimeout(librarySearchTimer);
    libraryKbIndex = -1;
    if (q.length < 2) {{ librarySearchResults.style.display = 'none'; libraryResults = []; return; }}
    librarySearchTimer = setTimeout(async () => {{
        const resp = await fetch('/api/search?q=' + encodeURIComponent(q));
        libraryResults = await resp.json();
        renderLibraryResults();
        librarySearchResults.style.display = 'block';
    }}, 250);
}});

librarySearchInput.addEventListener('keydown', (e) => {{
    if (e.key === 'Escape') {{
        librarySearchInput.value = '';
        libraryResults = [];
        librarySearchResults.style.display = 'none';
        return;
    }}
    if (!libraryResults.length || librarySearchResults.style.display === 'none') return;
    if (e.key === 'ArrowDown') {{
        e.preventDefault();
        libraryKbIndex = Math.min(libraryKbIndex + 1, libraryResults.length - 1);
        renderLibraryResults();
    }} else if (e.key === 'ArrowUp') {{
        e.preventDefault();
        libraryKbIndex = Math.max(libraryKbIndex - 1, 0);
        renderLibraryResults();
    }} else if (e.key === 'Enter') {{
        e.preventDefault();
        openLibraryResult(libraryKbIndex >= 0 ? libraryKbIndex : 0);
    }}
}});

document.addEventListener('click', (e) => {{
    if (!e.target.closest('#searchInput') && !e.target.closest('#searchResults')) librarySearchResults.style.display = 'none';
}});

onProviderChange();
loadProviderStatus();
renderRecentList();
</script>
</body>
</html>"""


def render_my_books_page(books: list) -> str:
    """The 'My Books' page: a separate list of books imported from a
    Goodreads-format CSV export. Grouped into two sections client-side --
    'Book Read' (date_read present) and 'Unsorted' (date_read empty) --
    with a per-row <input type="date"> for inline editing. Uses the same
    shared CSS/layout/header as the other pages; nothing here talks to
    the LNRelease `releases` table.

    The `books` argument is the full `db.get_imported_books()` result,
    serialized with `_safe_json_for_script` so a title/author containing
    `</script>` cannot escape the surrounding tag (same protection as
    every other page)."""
    books_json = _safe_json_for_script(books)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{APP_NAME} — My Books</title>
<link rel="icon" type="image/png" href="/static/favicon-32.png" sizes="32x32">
<link rel="icon" type="image/png" href="/static/favicon-64.png" sizes="64x64">
<script>{THEME_INIT_SCRIPT}</script>
<style>{BASE_CSS}</style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="header-left">
            <img class="header-icon" src="/static/icon.png" alt="">
            <h1>📚 My Books</h1>
            <span class="version-tag">v{VERSION}</span>
        </div>
        <div class="header-right">
            {THEME_TOGGLE_HTML}
            <a class="nav-link" href="/" title="Jump to current month/year">🏠 Home</a>
            <a class="nav-link" href="/starred">★ My Starred</a>
            <a class="nav-link" href="/add">➕ Add Book</a>
        </div>
    </div>

    <div class="add-section">
        <h2>📥 Import books from CSV</h2>
        <div class="import-row">
            <input type="file" id="csvFile" accept=".csv,text/csv">
            <button class="add-btn primary" id="importBtn" onclick="importCsv()">Import</button>
        </div>
        <div class="add-hint">
            Accepts a Goodreads CSV export. Only <b>Title</b>, <b>Author</b>,
            <b>Publisher</b>, <b>Year Published</b>, and <b>Date Read</b> are imported;
            all other columns are ignored. Books with a Date Read land under
            <b>Book Read</b>; books without one land under <b>Unsorted</b>.
        </div>
        <div id="importStatus" class="import-status"></div>
    </div>

    <div class="nav-bar">
        <div class="search-wrap" style="flex:1;">
            <input id="booksSearch" type="text" placeholder="Filter by title, author, or publisher..." autocomplete="off">
        </div>
        <span id="countLabel" style="font-size:.8rem;color:var(--text-dim);white-space:nowrap;"></span>
    </div>

    <div id="content"></div>
</div>

<script>
{THEME_TOGGLE_JS}

let books = {books_json};
let filterText = '';

function escapeHtml(s) {{
    return String(s == null ? '' : s).replace(/[&<>]/g, c => ({{'&': '&amp;', '<': '&lt;', '>': '&gt;'}}[c]));
}}
function escapeAttr(s) {{
    return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({{'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}}[c]));
}}

async function importCsv() {{
    const fileInput = document.getElementById('csvFile');
    const file = fileInput.files[0];
    const status = document.getElementById('importStatus');
    if (!file) {{ alert('Pick a CSV file first.'); return; }}
    status.innerHTML = '<span class="ok">Importing…</span>';
    const fd = new FormData();
    fd.append('file', file);
    let data;
    try {{
        const resp = await fetch('/api/import_books_csv', {{method: 'POST', body: fd}});
        if (!resp.ok) {{
            let msg = 'Import failed';
            try {{
                const j = await resp.json();
                msg = j.error || j.message || msg;
            }} catch (e) {{}}
            status.innerHTML = `<span class="err">${{escapeHtml(msg)}}</span>`;
            return;
        }}
        data = await resp.json();
    }} catch (e) {{
        status.innerHTML = '<span class="err">Could not upload — check your connection and try again.</span>';
        return;
    }}

    // Pull the fresh full list to reflect what was actually committed.
    let refreshed = false;
    try {{
        const resp = await fetch('/api/imported_books');
        if (resp.ok) {{ books = await resp.json(); refreshed = true; }}
    }} catch (e) {{}}

    let html = `<span class="ok">✓ Imported: ${{data.added}} new`;
    if (data.skipped) html += `, ${{data.skipped}} duplicate(s) skipped`;
    if (data.skipped_rows) html += `, ${{data.skipped_rows}} row(s) with no title skipped`;
    if (data.errors) html += `, ${{data.errors}} error(s)`;
    html += '.</span>';
    if (!refreshed) html += ' <span class="warn">(reload the page to see the new items)</span>';
    if (data.warnings && data.warnings.length) {{
        html += '<ul>' + data.warnings.slice(0, 20).map(w => `<li>${{escapeHtml(w)}}</li>`).join('') + '</ul>';
        if (data.warnings.length > 20) html += `<div class="add-hint">…and ${{data.warnings.length - 20}} more warnings</div>`;
    }}
    status.innerHTML = html;
    fileInput.value = '';
    render();
}}

async function setDateRead(id, value) {{
    // <input type="date"> always gives YYYY-MM-DD or "", so this is
    // belt-and-suspenders — but it also makes "cleared input" round-trip
    // to `null` (→ Unsorted) exactly as intended.
    let iso = value;
    if (iso && !/^\\d{{4}}-\\d{{2}}-\\d{{2}}$/.test(iso)) iso = null;
    if (!iso) iso = null;
    let resp;
    try {{
        resp = await fetch(`/api/imported_book/${{id}}/update`, {{
            method: 'POST', headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{date_read: iso}})
        }});
    }} catch (e) {{
        alert('Could not save — check your connection and try again.');
        return;
    }}
    if (!resp.ok) {{
        alert('Could not save that date. Check the format (YYYY-MM-DD).');
        return;
    }}
    const row = await resp.json();
    const book = books.find(b => b.id === id);
    if (book) {{ book.date_read = row.date_read; }}
    render();
}}

async function removeBook(id) {{
    if (!confirm('Remove this book from My Books?')) return;
    let resp;
    try {{
        resp = await fetch(`/api/imported_book/${{id}}/remove`, {{method: 'POST'}});
    }} catch (e) {{
        alert('Could not remove — check your connection and try again.');
        return;
    }}
    if (!resp.ok) {{ alert('Could not remove.'); return; }}
    books = books.filter(b => b.id !== id);
    render();
}}

function render() {{
    const q = filterText.toLowerCase();
    const filtered = q
        ? books.filter(b => ((b.title || '') + ' ' + (b.author || '') + ' ' + (b.publisher || '')).toLowerCase().includes(q))
        : books;
    const read = filtered.filter(b => b.date_read)
        .sort((a, b) => b.date_read < a.date_read ? -1 : b.date_read > a.date_read ? 1 : 0);
    const unsorted = filtered.filter(b => !b.date_read)
        .sort((a, b) => (a.title || '') < (b.title || '') ? -1 : (a.title || '') > (b.title || '') ? 1 : 0);

    document.getElementById('countLabel').textContent = books.length + ' books total';

    const content = document.getElementById('content');
    if (!books.length) {{
        content.innerHTML = '<div class="empty-state">No books imported yet. Use the form above to import a CSV.</div>';
        return;
    }}
    if (!filtered.length) {{
        content.innerHTML = '<div class="empty-state">No books match that search.</div>';
        return;
    }}

    function rowHtml(b) {{
        return `<tr data-id="${{b.id}}">
            <td class="col-title" data-label="Title">${{escapeHtml(b.title || '')}}</td>
            <td class="col-author" data-label="Author">${{escapeHtml(b.author || '')}}</td>
            <td class="col-publisher" data-label="Publisher">${{escapeHtml(b.publisher || '')}}</td>
            <td class="col-date" data-label="Date Published">${{escapeHtml(b.date_published || '')}}</td>
            <td class="col-status" data-label="Date Read">
                <input type="date" class="date-read-input" value="${{escapeAttr(b.date_read || '')}}"
                    onchange="setDateRead(${{b.id}}, this.value)">
            </td>
            <td class="col-edit"><button class="remove-row-btn" onclick="removeBook(${{b.id}})">Remove</button></td>
        </tr>`;
    }}

    let html = '';
    if (read.length) {{
        html += `<div class="section-header">📖 Book Read <span class="section-count">(${{read.length}})</span></div>
        <table>
            <thead><tr>
                <th class="col-title">Title</th>
                <th class="col-author">Author</th>
                <th class="col-publisher">Publisher</th>
                <th class="col-date">Date Published</th>
                <th class="col-status">Date Read</th>
                <th class="col-edit"></th>
            </tr></thead>
            <tbody>${{read.map(rowHtml).join('')}}</tbody>
        </table>`;
    }}
    if (unsorted.length) {{
        html += `<div class="section-header">📚 Unsorted <span class="section-count">(${{unsorted.length}})</span></div>
        <table>
            <thead><tr>
                <th class="col-title">Title</th>
                <th class="col-author">Author</th>
                <th class="col-publisher">Publisher</th>
                <th class="col-date">Date Published</th>
                <th class="col-status">Date Read</th>
                <th class="col-edit"></th>
            </tr></thead>
            <tbody>${{unsorted.map(rowHtml).join('')}}</tbody>
        </table>`;
    }}
    content.innerHTML = html;
}}

document.getElementById('booksSearch').addEventListener('input', (e) => {{
    filterText = e.target.value.trim();
    render();
}});

render();
</script>
</body>
</html>"""