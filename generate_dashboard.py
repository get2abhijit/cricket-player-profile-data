"""
generate_dashboard.py
---------------------
Reads output/dashboard_data.json and writes output/dashboard.html — a
self-contained static page (no server required) with embedded player data,
team filters, player cards, and summary stats.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DASHBOARD_DATA_PATH = Path("output/dashboard_data.json")
DASHBOARD_HTML_PATH = Path("output/dashboard.html")

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Global Player Dataset Dashboard</title>
  <style>
    :root {
      --green-dark:   #1b4332;
      --green-mid:    #2d6a4f;
      --green-light:  #52b788;
      --cream:        #f8f4e9;
      --amber:        #e9b949;
      --amber-dark:   #c58a00;
      --bg:           #f5f0e8;
      --card-bg:      #ffffff;
      --text:         #1a1a2e;
      --muted:        #6b7280;
      --border:       #d4c9b0;
      --badge-rhb:    #d1fae5;
      --badge-lhb:    #fef9c3;
      --badge-pace:   #fee2e2;
      --badge-spin:   #dbeafe;
      --badge-role:   #ede9fe;
      --badge-wk:     #ffe4e6;
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }
    /* ── Header ── */
    header {
      background: var(--green-dark);
      color: #fff;
      padding: 1.25rem 2rem;
      display: flex;
      align-items: center;
      gap: 0.75rem;
      box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }
    header h1 { font-size: 1.35rem; font-weight: 700; letter-spacing: 0.02em; }
    header p  { font-size: 0.8rem; color: #a7f3c8; margin-top: 0.15rem; }
    .header-icon { font-size: 1.8rem; }
    /* ── Summary bar ── */
    #summary {
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      padding: 1.25rem 2rem;
      background: var(--green-mid);
      color: #fff;
    }
    .stat-pill {
      background: rgba(255,255,255,0.15);
      border-radius: 999px;
      padding: 0.3rem 1rem;
      font-size: 0.82rem;
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }
    .stat-pill strong { font-size: 1rem; }
    /* ── Main content ── */
    main { padding: 1.5rem 2rem 3rem; }
    /* ── Search + sort bar ── */
    #controls {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: center;
      margin-bottom: 1.25rem;
    }
    #search {
      flex: 1; min-width: 200px;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.5rem 0.85rem;
      font-size: 0.9rem;
      background: var(--card-bg);
      outline: none;
      color: var(--text);
    }
    #search:focus { border-color: var(--green-light); box-shadow: 0 0 0 3px rgba(82,183,136,0.2); }
    /* ── Team filter pills ── */
    #team-filters {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-bottom: 1.5rem;
    }
    .team-pill {
      cursor: pointer;
      border: 1.5px solid var(--border);
      border-radius: 999px;
      padding: 0.3rem 1rem;
      font-size: 0.82rem;
      background: var(--card-bg);
      color: var(--text);
      transition: all 0.15s;
      white-space: nowrap;
    }
    .team-pill:hover { border-color: var(--green-light); color: var(--green-mid); }
    .team-pill.active {
      background: var(--green-mid);
      border-color: var(--green-mid);
      color: #fff;
      font-weight: 600;
    }
    /* ── Player grid ── */
    #player-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 1rem;
    }
    /* ── Player card ── */
    .player-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem 1.1rem;
      display: flex;
      flex-direction: column;
      gap: 0.6rem;
      transition: box-shadow 0.18s, transform 0.18s;
    }
    .player-card:hover {
      box-shadow: 0 4px 18px rgba(0,0,0,0.1);
      transform: translateY(-2px);
    }
    .card-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 0.5rem;
    }
    .player-name {
      font-weight: 700;
      font-size: 0.97rem;
      line-height: 1.25;
      color: var(--green-dark);
    }
    .player-id { font-size: 0.68rem; color: var(--muted); font-family: monospace; }
    .enriched-dot {
      width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; margin-top: 4px;
    }
    .enriched-dot.yes { background: var(--green-light); }
    .enriched-dot.no  { background: #d1d5db; }
    .card-teams {
      display: flex; flex-wrap: wrap; gap: 0.3rem;
    }
    .team-tag {
      font-size: 0.72rem;
      background: var(--cream);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.1rem 0.5rem;
      color: var(--green-dark);
      font-weight: 600;
    }
    .card-skills {
      display: flex; flex-wrap: wrap; gap: 0.35rem;
      margin-top: 0.1rem;
    }
    .badge {
      font-size: 0.72rem;
      border-radius: 6px;
      padding: 0.15rem 0.55rem;
      font-weight: 600;
    }
    .badge-rhb   { background: var(--badge-rhb); color: #065f46; }
    .badge-lhb   { background: var(--badge-lhb); color: #78350f; }
    .badge-pace  { background: var(--badge-pace); color: #991b1b; }
    .badge-spin  { background: var(--badge-spin); color: #1e40af; }
    .badge-role  { background: var(--badge-role); color: #5b21b6; }
    .badge-wk    { background: var(--badge-wk); color: #9f1239; }
    .badge-sub   { background: #f3f4f6; color: #374151; font-weight: 500; }
    .card-raw {
      font-size: 0.72rem; color: var(--muted);
      border-top: 1px solid var(--border);
      padding-top: 0.45rem;
      line-height: 1.5;
    }
    /* ── Empty state ── */
    #empty-state {
      display: none;
      flex-direction: column;
      align-items: center;
      padding: 4rem 2rem;
      color: var(--muted);
      text-align: center;
      grid-column: 1 / -1;
    }
    #empty-state.visible { display: flex; }
    /* ── Responsive ── */
    @media (max-width: 600px) {
      header, #summary, main { padding-left: 1rem; padding-right: 1rem; }
      #player-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>

<header>
  <span class="header-icon">🏏</span>
  <div>
    <h1>Global Player Dataset</h1>
    <p>Cricsheet registry + ESPN/Cricbuzz enrichment &mdash; global T20 dataset</p>
  </div>
</header>

<div id="summary"></div>

<main>
  <div id="view-tabs" style="display:flex;gap:0;margin-bottom:1.25rem;">
    <button class="view-tab active" data-view="enriched" style="flex:1;padding:0.6rem 1rem;border:1.5px solid var(--border);border-radius:8px 0 0 8px;background:var(--green-dark);color:#fff;cursor:pointer;font-weight:600;font-size:0.88rem;">🟢 Enriched Players</button>
    <button class="view-tab" data-view="missing" style="flex:1;padding:0.6rem 1rem;border:1.5px solid var(--border);border-left:none;border-radius:0 8px 8px 0;background:var(--card-bg);color:var(--text);cursor:pointer;font-weight:600;font-size:0.88rem;">⚠️ Missing Players</button>
  </div>
  <div id="enriched-view">
    <div id="controls">
      <input id="search" type="text" placeholder="Search player name…" autocomplete="off" />
    </div>
    <div id="team-filters"></div>
    <div id="player-grid">
      <div id="empty-state">
        <p style="font-size:2rem;">🔍</p>
        <p>No players match the current filters.</p>
      </div>
    </div>
  </div>
  <div id="missing-view" style="display:none;">
    <div id="missing-controls" style="margin-bottom:1rem;">
      <input id="missing-search" type="text" placeholder="Search missing player name…" autocomplete="off"
             style="width:100%;border:1px solid var(--border);border-radius:8px;padding:0.5rem 0.85rem;font-size:0.9rem;background:var(--card-bg);color:var(--text);" />
    </div>
    <div id="missing-content"></div>
  </div>
</main>

<script>
const DATA = __DASHBOARD_DATA__;

/////////////////////////////////////////////////////////////////////
// Helpers
/////////////////////////////////////////////////////////////////////
function esc(str) {
  return str == null ? '' : String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function badge(cls, text) {
  if (!text) return '';
  return `<span class="badge ${cls}">${esc(text)}</span>`;
}

/////////////////////////////////////////////////////////////////////
// State
/////////////////////////////////////////////////////////////////////
let activeTeam = '__all__';
let searchQuery = '';

/////////////////////////////////////////////////////////////////////
// Summary bar
/////////////////////////////////////////////////////////////////////
function renderSummary() {
  const players = DATA.players;
  // DATA.players already contains only enriched-classified players.
  const enriched = players.length;
  const rhb = players.filter(p => p.batting_hand === 'RHB').length;
  const lhb = players.filter(p => p.batting_hand === 'LHB').length;
  const pace = players.filter(p => p.bowling_type === 'Pace').length;
  const spin = players.filter(p => p.bowling_type === 'Spin').length;
  const unfound = DATA.unfound_players ? Object.values(DATA.unfound_players).reduce((s, a) => s + a.length, 0) : 0;
  const ignored = DATA.ignored_players ? Object.values(DATA.ignored_players).reduce((s, a) => s + a.length, 0) : 0;
  const total = enriched + unfound + ignored;
  const el = document.getElementById('summary');
  el.innerHTML = [
    `<div class="stat-pill"><strong>${total}</strong> players</div>`,
    `<div class="stat-pill"><strong>${DATA.teams.length}</strong> teams</div>`,
    `<div class="stat-pill">🟢 <strong>${enriched}</strong> enriched</div>`,
    `<div class="stat-pill">⚠️ <strong>${unfound}</strong> missing (actionable)</div>`,
    `<div class="stat-pill">🗂️ <strong>${ignored}</strong> ignored</div>`,
    `<div class="stat-pill">🏏 <strong>${rhb}</strong> RHB | <strong>${lhb}</strong> LHB</div>`,
    `<div class="stat-pill">⚡ <strong>${pace}</strong> Pace | 🌀 <strong>${spin}</strong> Spin</div>`,
  ].join('');
}

/////////////////////////////////////////////////////////////////////
// Team filter pills
/////////////////////////////////////////////////////////////////////
function renderFilters() {
  const container = document.getElementById('team-filters');
  const all = ['__all__', ...DATA.teams];
  container.innerHTML = all.map(t => {
    const label = t === '__all__' ? 'All Teams' : t;
    const count = t === '__all__'
      ? DATA.players.length
      : DATA.players.filter(p => p.teams && p.teams.includes(t)).length;
    const active = t === activeTeam ? 'active' : '';
    return `<button class="team-pill ${active}" data-team="${esc(t)}">${esc(label)} <span style="opacity:0.65">${count}</span></button>`;
  }).join('');

  container.querySelectorAll('.team-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      activeTeam = btn.dataset.team;
      renderFilters();
      renderGrid();
    });
  });
}

/////////////////////////////////////////////////////////////////////
// Player grid
/////////////////////////////////////////////////////////////////////
function buildCard(p) {
  const teams = (p.teams || []).map(t => `<span class="team-tag">${esc(t)}</span>`).join('');
  const enrichedClass = (p.batting_hand || p.bowling_type) ? 'yes' : 'no';

  const bats = p.batting_hand === 'RHB' ? badge('badge-rhb','RHB')
             : p.batting_hand === 'LHB' ? badge('badge-lhb','LHB') : '';
  const btype = p.bowling_type === 'Pace' ? badge('badge-pace', p.bowling_subtype || 'Pace')
              : p.bowling_type === 'Spin' ? badge('badge-spin', p.bowling_subtype || 'Spin') : '';
  const arm = p.bowling_arm ? badge('badge-sub', p.bowling_arm + ' arm') : '';
  const mech = p.bowling_mechanism && p.bowling_mechanism !== 'None'
               ? badge('badge-sub', p.bowling_mechanism) : '';
  const role = p.role ? badge('badge-role', p.role) : '';
  const wicketkeeper = p.is_wicketkeeper ? badge('badge-wk', 'WK') : '';
  const manual = p.manual_override ? badge('badge-sub', 'Manual') : '';

  const rawLines = [];
  if (p.raw_batting)  rawLines.push(`Bat: ${esc(p.raw_batting)}`);
  if (p.raw_bowling)  rawLines.push(`Bowl: ${esc(p.raw_bowling)}`);
  const rawSection = rawLines.length
    ? `<div class="card-raw">${rawLines.join(' &bull; ')}</div>` : '';

  const espnLink = p.source_url
    ? `<a href="${esc(p.source_url)}"
        target="_blank" rel="noopener" style="font-size:0.68rem;color:#2d6a4f;text-decoration:none;">Profile ↗</a>`
    : '';

  return `
    <div class="player-card">
      <div class="card-top">
        <div>
          <div class="player-name">${esc(p.name)}</div>
          <div class="player-id">${esc(p.id)} ${espnLink}</div>
        </div>
        <div class="enriched-dot ${enrichedClass}" title="${enrichedClass === 'yes' ? 'Data enriched' : 'No style data'}"></div>
      </div>
      ${teams ? `<div class="card-teams">${teams}</div>` : ''}
      <div class="card-skills">
        ${bats}${btype}${arm}${mech}${role}${wicketkeeper}${manual}
        ${!bats && !btype && !role && !wicketkeeper ? '<span style="font-size:0.72rem;color:#9ca3af;font-style:italic;">no skill data</span>' : ''}
      </div>
      ${rawSection}
    </div>`;
}

function renderGrid() {
  const q = searchQuery.toLowerCase();
  const filtered = DATA.players.filter(p => {
    const matchesTeam = activeTeam === '__all__' || (p.teams && p.teams.includes(activeTeam));
    const matchesSearch = !q || p.name.toLowerCase().includes(q);
    return matchesTeam && matchesSearch;
  });

  const grid = document.getElementById('player-grid');
  const empty = document.getElementById('empty-state');

  if (filtered.length === 0) {
    grid.innerHTML = '';
    grid.appendChild(empty);
    empty.classList.add('visible');
    return;
  }
  empty.classList.remove('visible');
  grid.innerHTML = filtered.map(buildCard).join('') + empty.outerHTML;
}

/////////////////////////////////////////////////////////////////////
// Search handler (debounced)
/////////////////////////////////////////////////////////////////////
let searchTimer;
document.getElementById('search').addEventListener('input', e => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    searchQuery = e.target.value.trim();
    renderGrid();
  }, 200);
});

/////////////////////////////////////////////////////////////////////
// Tab switching (Enriched / Missing)
/////////////////////////////////////////////////////////////////////
document.querySelectorAll('.view-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.view-tab').forEach(b => {
      b.classList.remove('active');
      b.style.background = 'var(--card-bg)';
      b.style.color = 'var(--text)';
    });
    btn.classList.add('active');
    btn.style.background = 'var(--green-dark)';
    btn.style.color = '#fff';

    const view = btn.dataset.view;
    document.getElementById('enriched-view').style.display = view === 'enriched' ? '' : 'none';
    document.getElementById('missing-view').style.display = view === 'missing' ? '' : 'none';
    if (view === 'missing') renderMissing();
  });
});

/////////////////////////////////////////////////////////////////////
// Missing players view
/////////////////////////////////////////////////////////////////////
let missingSearchQuery = '';

function renderMissing() {
  const container = document.getElementById('missing-content');
  const unfound = DATA.unfound_players || {};
  const ignored = DATA.ignored_players || {};
  const teams = Object.keys(unfound).sort();
  const ignoredTeams = Object.keys(ignored).sort();
  const q = missingSearchQuery.toLowerCase();

  if (teams.length === 0 && ignoredTeams.length === 0) {
    container.innerHTML = '<p style="text-align:center;color:var(--muted);padding:2rem;">No missing players recorded.</p>';
    return;
  }

  let html = '<div style="margin-bottom:1.25rem;padding:0.8rem 0.9rem;border:1px dashed var(--border);border-radius:8px;background:#fff7ed;color:#7c2d12;font-size:0.8rem;">Actionable missing players appear first. Ignored players are listed separately with a reason. Manual edits belong in data/manual_overrides.json; new missing-player placeholders are seeded there automatically.</div>';
  const actionableTotal = Object.values(unfound).reduce((s, a) => s + a.length, 0);
  html += `<h3 style="font-size:1rem;font-weight:700;color:var(--green-dark);margin-bottom:0.7rem;">Actionable Missing Players <span style="font-weight:400;color:var(--muted);font-size:0.85rem;">(${actionableTotal})</span></h3>`;

  let actionableHtml = '';
  for (const team of teams) {
    let players = unfound[team] || [];
    if (q) players = players.filter(p => (p.name || '').toLowerCase().includes(q));
    if (players.length === 0) continue;

    actionableHtml += `<div style="margin-bottom:1.2rem;">`;
    actionableHtml += `<h4 style="font-size:0.95rem;font-weight:700;color:var(--green-dark);margin-bottom:0.5rem;border-bottom:2px solid var(--border);padding-bottom:0.3rem;">${esc(team)} <span style="font-weight:400;color:var(--muted);font-size:0.85rem;">(${players.length})</span></h4>`;
    actionableHtml += `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:0.6rem;">`;

    for (const p of players) {
      const espnUrl = p.source_url || (p.espn_id ? 'https://www.espncricinfo.com/cricketers/_/id/' + esc(p.espn_id) : '');
      const espnLink = espnUrl ? `<a href="${esc(espnUrl)}" target="_blank" rel="noopener" style="font-size:0.68rem;color:#2d6a4f;">Profile ↗</a>` : '';
      actionableHtml += `<div style="background:var(--card-bg);border:1px solid var(--border);border-radius:8px;padding:0.6rem 0.9rem;">`;
      actionableHtml += `<div style="font-weight:600;font-size:0.88rem;">${esc(p.name)}</div>`;
      actionableHtml += `<div style="font-size:0.72rem;color:var(--muted);">ID: ${esc(p.id)}`;
      if (p.espn_id) actionableHtml += ` &bull; ESPN: ${esc(p.espn_id)}`;
      if (p.t20i_matches != null) actionableHtml += ` &bull; T20I matches: ${esc(p.t20i_matches)}`;
      actionableHtml += ` ${espnLink}</div>`;
      actionableHtml += `</div>`;
    }
    actionableHtml += `</div></div>`;
  }

  if (!actionableHtml) {
    html += '<p style="color:var(--muted);padding:0.4rem 0 1.2rem;">No actionable missing players match the search.</p>';
  } else {
    html += actionableHtml;
  }

  const ignoredTotal = Object.values(ignored).reduce((s, a) => s + a.length, 0);
  html += `<h3 style="font-size:1rem;font-weight:700;color:#92400e;margin:0.8rem 0 0.7rem;">Ignored Players <span style="font-weight:400;color:var(--muted);font-size:0.85rem;">(${ignoredTotal})</span></h3>`;

  const ignoredByReason = {};
  for (const team of ignoredTeams) {
    for (const p of ignored[team] || []) {
      if (q && !(p.name || '').toLowerCase().includes(q)) continue;
      const reason = p.ignore_reason || 'Ignored by filter';
      if (!ignoredByReason[reason]) ignoredByReason[reason] = {};
      if (!ignoredByReason[reason][team]) ignoredByReason[reason][team] = [];
      ignoredByReason[reason][team].push(p);
    }
  }

  const ignoredReasonOrder = ['No T20 appearance', 'No match since 2020-01-01', 'No profile available'];
  let ignoredHtml = '';
  for (const reason of ignoredReasonOrder) {
    const teamsForReason = ignoredByReason[reason] || {};
    const reasonTeams = Object.keys(teamsForReason).sort();
    const reasonCount = reasonTeams.reduce((s, team) => s + teamsForReason[team].length, 0);
    if (reasonCount === 0) continue;

    ignoredHtml += `<div style="margin-bottom:1.2rem;">`;
    ignoredHtml += `<h4 style="font-size:0.98rem;font-weight:700;color:#92400e;margin-bottom:0.6rem;">${esc(reason)} <span style="font-weight:400;color:var(--muted);font-size:0.85rem;">(${reasonCount})</span></h4>`;

    for (const team of reasonTeams) {
      const players = teamsForReason[team];
      ignoredHtml += `<div style="margin-bottom:1rem;">`;
      ignoredHtml += `<h5 style="font-size:0.9rem;font-weight:700;color:#92400e;margin-bottom:0.45rem;border-bottom:2px solid #fcd34d;padding-bottom:0.3rem;">${esc(team)} <span style="font-weight:400;color:var(--muted);font-size:0.82rem;">(${players.length})</span></h5>`;
      ignoredHtml += `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:0.6rem;">`;

      for (const p of players) {
        const profileUrl = p.source_url || (p.espn_id ? 'https://www.espncricinfo.com/cricketers/_/id/' + esc(p.espn_id) : '');
        const profileLink = profileUrl ? `<a href="${esc(profileUrl)}" target="_blank" rel="noopener" style="font-size:0.68rem;color:#2d6a4f;">Profile ↗</a>` : '';
        ignoredHtml += `<div style="background:#fffaf0;border:1px solid #fcd34d;border-radius:8px;padding:0.6rem 0.9rem;">`;
        ignoredHtml += `<div style="font-weight:600;font-size:0.88rem;">${esc(p.name)}</div>`;
        ignoredHtml += `<div style="font-size:0.72rem;color:var(--muted);">ID: ${esc(p.id)}`;
        if (p.espn_id) ignoredHtml += ` &bull; ESPN: ${esc(p.espn_id)}`;
        if (p.t20i_matches != null) ignoredHtml += ` &bull; T20I matches: ${esc(p.t20i_matches)}`;
        if (p.latest_match_date) ignoredHtml += ` &bull; Last match: ${esc(p.latest_match_date)}`;
        ignoredHtml += ` ${profileLink}</div>`;
        ignoredHtml += `</div>`;
      }

      ignoredHtml += `</div></div>`;
    }

    ignoredHtml += `</div>`;
  }

  if (!ignoredHtml) {
    html += '<p style="color:var(--muted);padding:0.4rem 0 0;">No ignored players match the search.</p>';
  } else {
    html += ignoredHtml;
  }

  if (!actionableHtml && !ignoredHtml) {
    html = '<p style="text-align:center;color:var(--muted);padding:2rem;">No missing players match the search.</p>';
  }

  container.innerHTML = html;
}

let missingSearchTimer;
document.getElementById('missing-search').addEventListener('input', e => {
  clearTimeout(missingSearchTimer);
  missingSearchTimer = setTimeout(() => {
    missingSearchQuery = e.target.value.trim();
    renderMissing();
  }, 200);
});

/////////////////////////////////////////////////////////////////////
// Boot
/////////////////////////////////////////////////////////////////////
renderSummary();
renderFilters();
renderGrid();
</script>
</body>
</html>
"""


def generate_dashboard(
    data_path: Path = DASHBOARD_DATA_PATH,
    output_path: Path = DASHBOARD_HTML_PATH,
) -> Path:
    if not data_path.exists():
        raise FileNotFoundError(f"Dashboard data not found: {data_path}")

    with data_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    # Embed JSON as a literal JS value — using json.dumps with ASCII escaping so
    # it is safe to inline inside a <script> tag (no </script> injection risk).
    escaped_json = json.dumps(data, ensure_ascii=True)

    html = _HTML_TEMPLATE.replace("__DASHBOARD_DATA__", escaped_json)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"Dashboard written to {output_path}")
    return output_path


if __name__ == "__main__":
    generate_dashboard()
