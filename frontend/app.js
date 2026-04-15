/**
 * OligoVoid — siRNA Chemical Modification Gap Intelligence
 * Frontend application. Pure vanilla JS.
 */

const API = '';

// ═══════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════

const SUGAR_MODS = ["2'-OMe", "2'-F", "LNA", "cEt", "DNA", "RNA", "UNA", "MOE"];
const SUGAR_ABBREV = { "2'-OMe": 'm', "2'-F": 'f', LNA: 'L', cEt: 'E', DNA: 'd', RNA: 'r', UNA: 'U', MOE: 'e' };
const ABBREV_TO_MOD = {};
Object.entries(SUGAR_ABBREV).forEach(([k, v]) => ABBREV_TO_MOD[v] = k);

const MOD_COLORS = {
  "2'-OMe": '#3b82f6',
  "2'-F":   '#22c55e',
  "LNA":    '#ef4444',
  "cEt":    '#f97316',
  "DNA":    '#a78bfa',
  "RNA":    '#8892b0',
  "UNA":    '#ec4899',
  "MOE":    '#f59e0b',
};

// ESC default pattern (alternating OMe/F)
const ESC_GUIDE = ["2'-OMe","2'-F","2'-OMe","2'-F","2'-OMe","2'-F","2'-OMe","2'-F","2'-OMe","2'-F","2'-OMe","2'-F","2'-OMe","2'-F","2'-OMe","2'-F","2'-OMe","2'-F","2'-OMe","2'-F","2'-OMe"];
const ESC_PASSENGER = [...ESC_GUIDE];
const ESC_BACKBONE_GUIDE = ["PS","PS","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PO","PS","PS"];
const ESC_BACKBONE_PASS = [...ESC_BACKBONE_GUIDE];

// Seed(2-8), Cleavage(10-11), Supplementary(13-16), Overhang(19-21) — 1-indexed
const SEED_RANGE = [2, 3, 4, 5, 6, 7, 8];
const CLEAVAGE_RANGE = [10, 11];
const SUPPL_RANGE = [13, 14, 15, 16];
const OVERHANG_RANGE = [19, 20, 21];

// ═══════════════════════════════════════════════════════
// CACHE
// ═══════════════════════════════════════════════════════

const CACHE_TTL = 3600000; // 1 hour

function cacheGet(key) {
  try {
    const item = JSON.parse(localStorage.getItem(`ov_${key}`));
    if (item && Date.now() - item.ts < CACHE_TTL) return item.data;
  } catch {}
  return null;
}

function cacheSet(key, data) {
  try {
    localStorage.setItem(`ov_${key}`, JSON.stringify({ ts: Date.now(), data }));
  } catch {}
}

// ═══════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════

let statsData = null;
let ontologyData = null;
let heatmapData = null;
let knownPatterns = null;

// Scorer state
let scorerGuide = [...ESC_GUIDE];
let scorerPassenger = [...ESC_PASSENGER];

// Designer state (map tab)
let designerGuide = [...ESC_GUIDE];
let designerPassenger = [...ESC_PASSENGER];

// Mod picker callback
let pickerCallback = null;

// ═══════════════════════════════════════════════════════
// API HELPERS
// ═══════════════════════════════════════════════════════

async function apiFetch(path, opts = {}) {
  const resp = await fetch(`${API}${path}`, opts);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }
  return resp.json();
}

// ═══════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', async () => {
  initNav();
  initFilterListeners();
  initDesigner();
  initScorer();
  initModPicker();
  initDMTLControls();

  // Load initial data in parallel
  await Promise.all([
    loadStats(),
    loadOntology(),
  ]);

  // Load first tab
  loadModificationMap();

  // Auto-refresh stats every 60s
  setInterval(loadStats, 60000);
});

// ═══════════════════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════════════════

function initNav() {
  document.querySelectorAll('.nav-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      document.querySelectorAll('.tab-panel').forEach(p => {
        p.classList.remove('active');
      });

      const panel = document.getElementById(`tab-${tab}`);
      if (panel) {
        panel.classList.add('active');
        // Trigger a reflow to restart the CSS transition
        void panel.offsetWidth;
      }

      // Lazy-load tab content
      if (tab === 'map') loadModificationMap();
      if (tab === 'voids') loadVoids();
      if (tab === 'dmtl') loadDMTL();
      if (tab === 'velocity') loadVelocity();
      if (tab === 'scorer') initScorerPositions();
    });
  });
}

// ═══════════════════════════════════════════════════════
// STATS (Header chips)
// ═══════════════════════════════════════════════════════

async function loadStats() {
  try {
    const cached = cacheGet('stats');
    statsData = cached || await apiFetch('/api/stats');
    if (!cached) cacheSet('stats', statsData);
    renderHeaderChips();
  } catch (err) {
    showToast('Failed to load stats', true);
  }
}

function renderHeaderChips() {
  if (!statsData) return;
  const s = statsData;
  setChip('chip-explored', `${s.modification_space_explored_pct || 0}%`);
  setChip('chip-voids', s.total_void_candidates || 0);
  setChip('chip-highscore', s.voids_scored || 0);

  // Count warming from velocity data if available
  const warmCount = cacheGet('warming_count');
  setChip('chip-warming', warmCount || '—');
}

function setChip(id, value) {
  const chip = document.getElementById(id);
  if (chip) chip.querySelector('.chip-value').textContent = value;
}

// ═══════════════════════════════════════════════════════
// ONTOLOGY
// ═══════════════════════════════════════════════════════

async function loadOntology() {
  try {
    const cached = cacheGet('ontology');
    ontologyData = cached || await apiFetch('/api/ontology');
    if (!cached) cacheSet('ontology', ontologyData);
  } catch {}
}

// ═══════════════════════════════════════════════════════
// TAB 1: MODIFICATION MAP + HEATMAP
// ═══════════════════════════════════════════════════════

async function loadModificationMap() {
  if (heatmapData) {
    // Already loaded — skip unless we want to refresh
    return;
  }
  try {
    const cached = cacheGet('modmap');
    heatmapData = cached || await apiFetch('/api/modification-map');
    if (!cached) cacheSet('modmap', heatmapData);

    // Also load known patterns for tooltips
    if (!knownPatterns) {
      const kpCached = cacheGet('known_patterns');
      const kpData = kpCached || await apiFetch('/api/known-patterns');
      if (!kpCached) cacheSet('known_patterns', kpData);
      knownPatterns = kpData.patterns || [];
    }

    renderHeatmap('guide', heatmapData.guide_strand, 'heatmap-guide', 'heatmap-y-axis-guide');
    renderHeatmap('passenger', heatmapData.passenger_strand, 'heatmap-passenger', 'heatmap-y-axis-passenger');
    renderVoidCallout();
  } catch (err) {
    showToast('Failed to load modification map', true);
  }
}

function getHeatmapColor(count) {
  if (count === 0) return '#ff3366';
  if (count <= 2) return '#ff6600';
  if (count <= 5) return '#ffaa00';
  if (count <= 10) return '#88ff44';
  return '#00ff88';
}

function getHeatmapTextColor(count) {
  if (count === 0) return '#ffffff';
  if (count <= 5) return '#000000';
  return '#000000';
}

function getRegionClass(pos1indexed, strand) {
  if (strand !== 'guide') return '';
  if (SEED_RANGE.includes(pos1indexed)) return 'seed-region';
  if (CLEAVAGE_RANGE.includes(pos1indexed)) return 'cleavage-site';
  if (OVERHANG_RANGE.includes(pos1indexed)) return 'overhang';
  return '';
}

// Build a lookup for void positions
function buildVoidSet() {
  const voids = new Set();
  if (heatmapData && heatmapData.void_positions) {
    heatmapData.void_positions.forEach(v => {
      voids.add(`${v.strand}:${v.position}:${v.modification}`);
    });
  }
  return voids;
}

function renderHeatmap(strand, strandData, gridId, yAxisId) {
  const grid = document.getElementById(gridId);
  const yAxis = document.getElementById(yAxisId);
  if (!grid || !yAxis) return;

  const voidSet = buildVoidSet();

  // Y-axis labels (modification names)
  yAxis.innerHTML = '';
  const yHeader = document.createElement('div');
  yHeader.className = 'heatmap-y-label';
  yHeader.style.height = '22px';
  yHeader.textContent = '';
  yAxis.appendChild(yHeader);

  SUGAR_MODS.forEach(mod => {
    const label = document.createElement('div');
    label.className = 'heatmap-y-label';
    label.textContent = mod;
    label.style.color = MOD_COLORS[mod] || '#888';
    yAxis.appendChild(label);
  });

  // Grid: column headers (positions 1-21)
  grid.innerHTML = '';

  // Position header row
  const headerRow = document.createElement('div');
  headerRow.className = 'heatmap-row-header';
  for (let pos = 1; pos <= 21; pos++) {
    const label = document.createElement('div');
    label.className = 'heatmap-col-label';
    label.textContent = pos;
    headerRow.appendChild(label);
  }
  grid.appendChild(headerRow);

  // One row per modification
  SUGAR_MODS.forEach((mod, modIdx) => {
    const row = document.createElement('div');
    row.className = 'heatmap-row';

    for (let pos = 1; pos <= 21; pos++) {
      const posKey = `position_${pos}`;
      const count = (strandData[posKey] && strandData[posKey][mod]) || 0;
      const isVoid = voidSet.has(`${strand}:${pos}:${mod}`);

      const cell = document.createElement('div');
      cell.className = 'heatmap-cell';
      cell.style.background = getHeatmapColor(count);
      cell.style.color = getHeatmapTextColor(count);
      cell.textContent = count > 0 ? count : '';

      if (isVoid || count === 0) {
        cell.classList.add('void-cell');
      }

      // Region class
      const regionCls = getRegionClass(pos, strand);
      if (regionCls) cell.classList.add(regionCls);

      // Staggered animation
      const delay = (modIdx * 21 + pos) * 8;
      cell.style.opacity = '0';
      cell.style.transform = 'scale(0.8)';
      setTimeout(() => {
        cell.style.transition = 'opacity 0.3s, transform 0.3s';
        cell.style.opacity = '1';
        cell.style.transform = 'scale(1)';
      }, delay);

      // Data attributes for tooltip
      cell.dataset.strand = strand;
      cell.dataset.pos = pos;
      cell.dataset.mod = mod;
      cell.dataset.count = count;

      // Events
      cell.addEventListener('mouseenter', showHeatmapTooltip);
      cell.addEventListener('mouseleave', hideHeatmapTooltip);
      cell.addEventListener('click', handleHeatmapClick);

      row.appendChild(cell);
    }

    grid.appendChild(row);
  });
}

function showHeatmapTooltip(e) {
  const cell = e.currentTarget;
  const tooltip = document.getElementById('heatmap-tooltip');
  const strand = cell.dataset.strand;
  const pos = parseInt(cell.dataset.pos);
  const mod = cell.dataset.mod;
  const count = parseInt(cell.dataset.count);

  const strandLabel = strand === 'guide' ? 'Guide' : 'Passenger';
  let regionNote = '';
  if (strand === 'guide') {
    if (SEED_RANGE.includes(pos)) regionNote = ' (seed region)';
    else if (CLEAVAGE_RANGE.includes(pos)) regionNote = ' (cleavage site)';
    else if (OVERHANG_RANGE.includes(pos)) regionNote = ' (3\' overhang)';
  }

  // Find which known patterns use this combo
  let examples = '';
  if (knownPatterns && count > 0) {
    const matching = knownPatterns.filter(p => {
      const mods = strand === 'guide' ? p.guide_modifications : p.passenger_modifications;
      return mods && mods[pos - 1] === mod;
    }).map(p => p.drug_name).slice(0, 3);
    if (matching.length) examples = matching.join(', ');
  }

  tooltip.innerHTML = `
    <div class="tt-title">Position ${pos}, ${strandLabel} strand${regionNote}</div>
    <div>${mod} modification</div>
    <div class="tt-count">Tested in: ${count} published siRNAs</div>
    ${count === 0 ? '<div style="color:#ff3366;font-weight:700;margin-top:0.2rem;">VOID — Never tested</div>' : ''}
    ${examples ? `<div class="tt-examples">Examples: ${examples}</div>` : ''}
  `;

  tooltip.style.display = 'block';
  positionTooltip(tooltip, e);
}

function hideHeatmapTooltip() {
  document.getElementById('heatmap-tooltip').style.display = 'none';
}

function positionTooltip(tooltip, e) {
  const x = e.clientX + 12;
  const y = e.clientY + 12;
  tooltip.style.left = Math.min(x, window.innerWidth - 300) + 'px';
  tooltip.style.top = Math.min(y, window.innerHeight - 150) + 'px';
}

function handleHeatmapClick(e) {
  const cell = e.currentTarget;
  const mod = cell.dataset.mod;
  const strand = cell.dataset.strand;

  // Highlight all void cells in that row (same mod)
  const gridId = strand === 'guide' ? 'heatmap-guide' : 'heatmap-passenger';
  const grid = document.getElementById(gridId);
  const cells = grid.querySelectorAll('.heatmap-cell');

  cells.forEach(c => c.classList.remove('row-highlighted'));
  cells.forEach(c => {
    if (c.dataset.mod === mod && parseInt(c.dataset.count) === 0) {
      c.classList.add('row-highlighted');
    }
  });
}

function renderVoidCallout() {
  const callout = document.getElementById('void-callout');
  if (!statsData || !statsData.position_coverage) {
    callout.style.display = 'none';
    return;
  }

  const hot = statsData.position_coverage.hottest_void;
  if (!hot) {
    callout.style.display = 'none';
    return;
  }

  callout.innerHTML = `
    <strong>Most interesting void:</strong> ${hot.position}, ${hot.mod}<br>
    ${hot.why_interesting}
  `;
}

// ═══════════════════════════════════════════════════════
// INLINE PATTERN DESIGNER (Map tab)
// ═══════════════════════════════════════════════════════

function initDesigner() {
  const guideRow = document.getElementById('designer-guide');
  const passRow = document.getElementById('designer-passenger');
  if (!guideRow || !passRow) return;

  buildDesignerRow(guideRow, designerGuide, 'designer-guide');
  buildDesignerRow(passRow, designerPassenger, 'designer-passenger');

  document.getElementById('btn-analyze-pattern')?.addEventListener('click', analyzeDesignerPattern);

  updateDesignerPreview();
}

function buildDesignerRow(container, mods, prefix) {
  container.innerHTML = '';
  mods.forEach((mod, i) => {
    const sel = document.createElement('select');
    sel.className = 'designer-select';
    sel.dataset.index = i;
    sel.dataset.prefix = prefix;
    sel.style.background = modBg(mod);
    sel.style.color = MOD_COLORS[mod] || '#888';
    sel.style.borderColor = (MOD_COLORS[mod] || '#888') + '40';

    SUGAR_MODS.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m;
      opt.textContent = SUGAR_ABBREV[m];
      if (m === mod) opt.selected = true;
      sel.appendChild(opt);
    });

    sel.addEventListener('change', (e) => {
      const idx = parseInt(e.target.dataset.index);
      const newMod = e.target.value;
      if (prefix === 'designer-guide') designerGuide[idx] = newMod;
      else designerPassenger[idx] = newMod;
      e.target.style.background = modBg(newMod);
      e.target.style.color = MOD_COLORS[newMod] || '#888';
      e.target.style.borderColor = (MOD_COLORS[newMod] || '#888') + '40';
      updateDesignerPreview();
    });

    container.appendChild(sel);
  });
}

function modBg(mod) {
  const c = MOD_COLORS[mod] || '#888';
  return c + '18';
}

function updateDesignerPreview() {
  const preview = document.getElementById('score-preview');
  if (!preview) return;

  // Calculate biophysics locally for real-time preview
  const scores = localBiophysicsScore(designerGuide, designerPassenger);
  preview.innerHTML = Object.entries(scores).map(([label, val]) => {
    const cls = val >= 75 ? 'score-high' : val >= 50 ? 'score-mid' : 'score-low';
    return `<div class="score-mini">
      <span class="score-mini-value ${cls}">${val.toFixed(0)}</span>
      <span class="score-mini-label">${label}</span>
    </div>`;
  }).join('');
}

async function analyzeDesignerPattern() {
  const btn = document.getElementById('btn-analyze-pattern');
  btn.disabled = true;
  btn.textContent = 'Analyzing...';

  const conjugate = document.getElementById('designer-conjugate').value;
  try {
    const result = await apiFetch('/api/score/custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        guide_modifications: designerGuide,
        passenger_modifications: designerPassenger,
        backbone_guide: ESC_BACKBONE_GUIDE,
        backbone_passenger: ESC_BACKBONE_PASS,
        conjugate,
      }),
    });

    renderScoreCardFull(result, 'score-card-full');
    document.getElementById('score-card-full').style.display = 'block';
  } catch (err) {
    showToast(err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Analyze This Pattern';
  }
}

// ═══════════════════════════════════════════════════════
// LOCAL BIOPHYSICS (real-time preview)
// ═══════════════════════════════════════════════════════

const DELTA_TM = { "2'-OMe": 1.0, "2'-F": 1.8, LNA: 4.0, cEt: 3.5, DNA: -1.5, RNA: 0.0, UNA: -2.0, MOE: 2.0 };
const RISC_TOL = { "2'-OMe": 0.95, "2'-F": 0.9, LNA: 0.45, cEt: 0.5, DNA: 0.7, RNA: 1.0, UNA: 0.85, MOE: 0.4 };

function localBiophysicsScore(guide, passenger) {
  // Thermodynamic
  const allMods = [...guide, ...passenger];
  const nPos = allMods.length;
  const totalDeltaTm = allMods.reduce((sum, m) => sum + (DELTA_TM[m] || 0), 0);
  const avgPerPos = nPos > 0 ? totalDeltaTm / nPos : 0;
  const effectiveDelta = avgPerPos * Math.sqrt(nPos);
  let thermoScore;
  if (effectiveDelta >= 5 && effectiveDelta <= 15) thermoScore = 100 - Math.abs(effectiveDelta - 10) * 2;
  else if (effectiveDelta < 5) thermoScore = Math.max(0, 60 + effectiveDelta * 8);
  else thermoScore = Math.max(0, 100 - (effectiveDelta - 15) * 4);
  thermoScore = Math.min(100, Math.max(0, thermoScore));

  // RISC loading
  let riscScore = 100;
  const seedMods = guide.slice(1, 8); // positions 2-8 (0-indexed: 1-7)
  seedMods.forEach(m => {
    if (m === 'LNA') riscScore -= 15;
    if (m === 'cEt') riscScore -= 12;
    if (m === 'MOE') riscScore -= 10;
  });
  const cleavMods = guide.slice(9, 11); // positions 10-11
  cleavMods.forEach(m => {
    if (['LNA', 'cEt', 'MOE'].includes(m)) riscScore -= 25;
  });
  if (guide[0] === 'UNA') riscScore += 8;
  const rigidCount = guide.filter(m => ['LNA', 'cEt', 'MOE'].includes(m)).length;
  if (rigidCount / 21 > 0.3) riscScore -= 15;
  riscScore = Math.min(100, Math.max(0, riscScore));

  // Nuclease resistance
  let nucScore = 40; // base
  const omeCount = allMods.filter(m => m === "2'-OMe").length;
  nucScore += Math.min(20, omeCount * 2);
  const rnaCount = allMods.filter(m => m === 'RNA').length;
  nucScore -= Math.min(30, rnaCount * 5);
  const lnaCount = allMods.filter(m => ['LNA', 'cEt'].includes(m)).length;
  nucScore += Math.min(15, lnaCount * 5);
  nucScore = Math.min(100, Math.max(0, nucScore));

  // Off-target risk (lower = better)
  let offTarget = 30; // base
  const passSeedMods = passenger.slice(1, 8);
  const passOmeInSeed = passSeedMods.filter(m => m === "2'-OMe").length;
  offTarget -= passOmeInSeed * 3;
  offTarget = Math.min(100, Math.max(0, offTarget));
  const offTargetScore = 100 - offTarget; // invert for display

  // Overall
  const overall = thermoScore * 0.20 + riscScore * 0.35 + nucScore * 0.25 + offTargetScore * 0.20;

  return {
    Thermo: thermoScore,
    RISC: riscScore,
    NucRes: nucScore,
    OffTgt: offTargetScore,
    Overall: overall,
  };
}

// ═══════════════════════════════════════════════════════
// TAB 2: TOP VOIDS
// ═══════════════════════════════════════════════════════

function initFilterListeners() {
  const minScore = document.getElementById('filter-min-score');
  const minScoreVal = document.getElementById('filter-min-score-value');
  if (minScore) {
    minScore.addEventListener('input', () => {
      minScoreVal.textContent = minScore.value;
    });
    minScore.addEventListener('change', loadVoids);
  }

  document.getElementById('filter-void-type')?.addEventListener('change', loadVoids);
  document.getElementById('filter-sort')?.addEventListener('change', loadVoids);
}

async function loadVoids() {
  const container = document.getElementById('void-cards');
  if (!container) return;

  const minScore = document.getElementById('filter-min-score')?.value || 0;
  const voidType = document.getElementById('filter-void-type')?.value || '';
  const sortBy = document.getElementById('filter-sort')?.value || 'overall_oligovoid_score';

  container.innerHTML = '<div class="no-data"><div class="spinner"></div> Loading voids...</div>';

  try {
    let url = `/api/voids?limit=50&min_score=${minScore}&sort_by=${sortBy}`;
    if (voidType) url += `&void_type=${voidType}`;

    const data = await apiFetch(url);
    const voids = data.voids || [];

    if (!voids.length) {
      container.innerHTML = '<div class="no-data">No voids match these filters.</div>';
      return;
    }

    container.innerHTML = '';
    voids.forEach((v, idx) => {
      container.appendChild(createVoidCard(v, idx + 1));
    });

    // Animate score bars
    requestAnimationFrame(() => {
      container.querySelectorAll('.score-bar-fill').forEach(bar => {
        bar.style.width = bar.dataset.width;
      });
    });
  } catch (err) {
    container.innerHTML = `<div class="no-data" style="color:var(--void-untested);">Error: ${err.message}</div>`;
  }
}

function createVoidCard(v, rank) {
  const card = document.createElement('div');
  card.className = 'void-card';

  const overallScore = v.overall_oligovoid_score || 0;
  const scoreColor = scoreColorFn(overallScore);

  const classification = v.classification || {};
  const voidType = classification.void_type || 'unknown';
  const risk = classification.exploration_risk || 'unknown';
  const complexity = classification.estimated_synthesis_complexity || 'unknown';

  const scores = [
    { label: 'RISC', value: v.risc_loading_score, key: 'risc' },
    { label: 'Stability', value: v.thermodynamic_score, key: 'thermo' },
    { label: 'NucRes', value: v.nuclease_resistance_score, key: 'nucres' },
    { label: 'Off-target', value: v.off_target_risk_score ? (100 - v.off_target_risk_score) : null, key: 'offtgt' },
  ];

  card.innerHTML = `
    <div class="void-card-header">
      <div>
        <span class="void-rank">#${rank}</span>
        <span class="void-id">${v.void_id}</span>
      </div>
      <div style="text-align:right;">
        <div class="void-overall-score" style="color:${scoreColor}">${overallScore.toFixed(0)}</div>
        <div class="void-overall-label">Score</div>
      </div>
    </div>

    <div class="void-notation">
      <span class="strand-label-inline">Guide:</span>
      <span class="notation-chars">5'-${colorizeNotation(v.guide_notation || '')}-3'</span>
    </div>
    <div class="void-notation">
      <span class="strand-label-inline">Pass:</span>
      <span class="notation-chars">3'-${colorizeNotation(v.passenger_notation || '')}-5'${v.conjugate ? ` <span style="color:var(--accent-purple);font-size:0.62rem;">[${v.conjugate}]</span>` : ''}</span>
    </div>

    ${v.description ? `<div class="void-description">${v.description}</div>` : ''}

    ${v.one_line_insight ? `<div class="void-insight">"${v.one_line_insight}"</div>` : ''}

    <div class="score-bars">
      ${scores.map(s => {
        if (s.value == null) return '';
        const c = scoreColorFn(s.value);
        const cls = s.value >= 75 ? 'bg-score-high' : s.value >= 50 ? 'bg-score-mid' : 'bg-score-low';
        return `<div class="score-bar-item">
          <div class="score-bar-top">
            <span class="score-bar-label">${s.label}</span>
            <span class="score-bar-value" style="color:${c}">${s.value.toFixed(0)}</span>
          </div>
          <div class="score-bar-track">
            <div class="score-bar-fill ${cls}" data-width="${s.value}%" style="width:0%"></div>
          </div>
        </div>`;
      }).join('')}
    </div>

    <div class="void-overall-bar">
      <div class="score-bar-top">
        <span class="score-bar-label">Overall OligoVoid Score</span>
        <span class="score-bar-value" style="color:${scoreColor}">${overallScore.toFixed(0)}/100</span>
      </div>
      <div class="score-bar-track">
        <div class="score-bar-fill" data-width="${overallScore}%" style="width:0%;background:${scoreColor}"></div>
      </div>
    </div>

    ${v.closest_known_pattern_id ? `
    <div class="void-nearest">
      Nearest drug: <strong style="color:var(--accent-cyan)">${v.closest_known_pattern_id}</strong>
      (${v.hamming_distance_to_nearest || '?'} positions differ)
    </div>` : ''}

    <div class="void-badges">
      <span class="void-badge ${risk === 'low' ? 'feasibility-high' : risk === 'medium' ? 'feasibility-medium' : 'feasibility-low'}">${risk === 'low' ? 'High' : risk === 'medium' ? 'Medium' : 'Low'} Feasibility</span>
      <span class="void-badge type-badge">${formatVoidType(voidType)}</span>
      ${complexity ? `<span class="void-badge" style="border-color:var(--border-bright);color:var(--text-secondary);">${complexity}</span>` : ''}
    </div>

    ${v.recommended_experiment ? `
    <div class="void-experiment">
      <strong>First experiment:</strong><br>
      "${v.recommended_experiment}"
    </div>` : ''}

    <button class="void-expand-btn" onclick="toggleVoidExpand(this)">&#9660; More</button>
    <div class="void-expanded">
      ${v.why_untested ? `<p style="margin-bottom:0.4rem;"><strong style="color:var(--accent-cyan);font-size:0.65rem;text-transform:uppercase;">Why never tested:</strong><br><span style="color:var(--text-secondary);font-size:0.72rem;">${v.why_untested}</span></p>` : ''}
      ${v.confidence_level ? `<p style="margin-bottom:0.4rem;"><strong style="color:var(--accent-cyan);font-size:0.65rem;text-transform:uppercase;">Confidence:</strong> <span class="mono" style="color:${v.confidence_level === 'high' ? 'var(--accent-biolum)' : 'var(--void-warming)'}">${v.confidence_level}</span></p>` : ''}
      ${v.predicted_knockdown_pct ? `<p><strong style="color:var(--accent-cyan);font-size:0.65rem;text-transform:uppercase;">Predicted Knockdown:</strong> <span class="mono color-green">${v.predicted_knockdown_pct}%</span></p>` : ''}
    </div>
  `;

  return card;
}

function toggleVoidExpand(btn) {
  const expanded = btn.nextElementSibling;
  expanded.classList.toggle('show');
  btn.innerHTML = expanded.classList.contains('show') ? '&#9650; Less' : '&#9660; More';
}

function colorizeNotation(notation) {
  return notation.split('').map(ch => {
    const mod = ABBREV_TO_MOD[ch];
    if (mod) {
      return `<span style="color:${MOD_COLORS[mod]}">${ch}</span>`;
    }
    return ch;
  }).join('');
}

function formatVoidType(type) {
  return (type || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function scoreColorFn(val) {
  if (val >= 75) return '#00ff88';
  if (val >= 50) return '#ff8800';
  return '#ff3366';
}

// ═══════════════════════════════════════════════════════
// TAB 3: DMTL
// ═══════════════════════════════════════════════════════

function initDMTLControls() {
  const slider = document.getElementById('dmtl-cycles');
  const label = document.getElementById('dmtl-cycles-value');
  if (slider) {
    slider.addEventListener('input', () => {
      label.textContent = slider.value;
    });
  }

  document.getElementById('btn-run-dmtl')?.addEventListener('click', runDMTLSimulation);
}

async function loadDMTL() {
  try {
    const data = await apiFetch('/api/dmtl/latest');
    if (data && data.cycles && data.cycles.length) {
      renderDMTLResults(data);
    }
  } catch {}
}

async function runDMTLSimulation() {
  const btn = document.getElementById('btn-run-dmtl');
  const loading = document.getElementById('dmtl-loading');
  const counter = document.getElementById('dmtl-cycle-counter');
  const acqFn = document.getElementById('dmtl-acq-fn').value;
  const nCycles = parseInt(document.getElementById('dmtl-cycles').value);

  btn.disabled = true;
  loading.style.display = 'flex';
  counter.textContent = '0';

  // Animate counter
  let currentCount = 0;
  const counterInterval = setInterval(() => {
    if (currentCount < nCycles) {
      currentCount++;
      counter.textContent = currentCount;
    }
  }, 800);

  try {
    const data = await apiFetch('/api/dmtl/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ acquisition_function: acqFn, n_cycles: nCycles }),
    });

    clearInterval(counterInterval);
    counter.textContent = nCycles;
    loading.style.display = 'none';

    renderDMTLResults(data);
  } catch (err) {
    clearInterval(counterInterval);
    loading.style.display = 'none';
    showToast('DMTL simulation failed: ' + err.message, true);
  } finally {
    btn.disabled = false;
  }
}

function renderDMTLResults(data) {
  const timeline = document.getElementById('dmtl-timeline');
  const summary = document.getElementById('dmtl-summary');
  const cycles = data.cycles || [];

  // Timeline
  timeline.innerHTML = '';
  cycles.forEach((c, idx) => {
    const card = document.createElement('div');
    card.className = 'dmtl-cycle-card';

    const infoGain = c.info_gain || 0;
    const uncBefore = c.uncertainty_before || 0;
    const uncAfter = c.uncertainty_after || 0;

    card.innerHTML = `
      <div class="dmtl-cycle-num">${c.cycle}</div>
      <div class="dmtl-cycle-body">
        <div class="dmtl-cycle-void">Recommend ${c.void_tested}</div>
        <div class="dmtl-cycle-reason">${truncate(c.reason || 'Active learning selection', 120)}</div>
        <div class="dmtl-cycle-stats">
          <span class="dmtl-cycle-stat">Uncertainty: <span class="val">${uncBefore.toFixed(3)} → ${uncAfter.toFixed(3)}</span></span>
          <span class="dmtl-cycle-stat">Info gain: <span class="val">${infoGain.toFixed(4)}</span></span>
        </div>
      </div>
    `;

    timeline.appendChild(card);

    // Staggered appearance
    setTimeout(() => card.classList.add('visible'), idx * 500);
  });

  // Coverage curve
  drawCoverageCurve(cycles);

  // Summary
  if (data.summary) {
    const s = data.summary;
    const reduction = s.uncertainty_reduction_pct;
    summary.innerHTML = `
      <strong>${data.title || 'DMTL Results'}</strong><br>
      ${s.total_cycles} cycles completed.
      ${reduction != null ? `Uncertainty reduced by <strong>${reduction.toFixed(1)}%</strong>.` : ''}
      ${cycles.length > 0 ? `<br>First cycle info gain: <strong>${(cycles[0].info_gain || 0).toFixed(4)}</strong>. Last cycle: <strong>${(cycles[cycles.length - 1].info_gain || 0).toFixed(4)}</strong> (diminishing returns = model converging).` : ''}
    `;
  }
}

function drawCoverageCurve(cycles) {
  const canvas = document.getElementById('coverage-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = 280 * dpr;
  canvas.style.width = rect.width + 'px';
  canvas.style.height = '280px';
  ctx.scale(dpr, dpr);

  const W = rect.width;
  const H = 280;
  const padLeft = 60;
  const padRight = 20;
  const padTop = 20;
  const padBottom = 40;
  const plotW = W - padLeft - padRight;
  const plotH = H - padTop - padBottom;

  // Clear
  ctx.clearRect(0, 0, W, H);

  if (!cycles.length) return;

  // Data points: uncertainty over cycles
  const points = cycles.map(c => c.uncertainty_before || 0);
  points.push(cycles[cycles.length - 1].uncertainty_after || 0);

  const maxUncertainty = Math.max(...points, 0.6);

  // Grid
  ctx.strokeStyle = '#1e2840';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 5; i++) {
    const y = padTop + (plotH / 5) * i;
    ctx.beginPath();
    ctx.moveTo(padLeft, y);
    ctx.lineTo(padLeft + plotW, y);
    ctx.stroke();
  }

  // Y axis labels
  ctx.fillStyle = '#8892b0';
  ctx.font = '11px "Space Mono", monospace';
  ctx.textAlign = 'right';
  for (let i = 0; i <= 5; i++) {
    const val = maxUncertainty * (1 - i / 5);
    const y = padTop + (plotH / 5) * i;
    ctx.fillText(val.toFixed(2), padLeft - 8, y + 4);
  }

  // X axis labels
  ctx.textAlign = 'center';
  for (let i = 0; i < points.length; i++) {
    const x = padLeft + (plotW / (points.length - 1)) * i;
    ctx.fillText(i === 0 ? 'Start' : `C${i}`, x, H - padBottom + 18);
  }

  // Line
  ctx.strokeStyle = '#00ff88';
  ctx.lineWidth = 2;
  ctx.lineJoin = 'round';
  ctx.beginPath();
  points.forEach((val, i) => {
    const x = padLeft + (plotW / (points.length - 1)) * i;
    const y = padTop + plotH * (1 - val / maxUncertainty);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Glow effect
  ctx.strokeStyle = 'rgba(0, 255, 136, 0.2)';
  ctx.lineWidth = 6;
  ctx.beginPath();
  points.forEach((val, i) => {
    const x = padLeft + (plotW / (points.length - 1)) * i;
    const y = padTop + plotH * (1 - val / maxUncertainty);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Dots
  ctx.fillStyle = '#00ff88';
  points.forEach((val, i) => {
    const x = padLeft + (plotW / (points.length - 1)) * i;
    const y = padTop + plotH * (1 - val / maxUncertainty);
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fill();
  });

  // Axis labels
  ctx.fillStyle = '#8892b0';
  ctx.font = '11px Inter, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('DMTL Cycle', W / 2, H - 4);

  ctx.save();
  ctx.translate(14, H / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText('Uncertainty', 0, 0);
  ctx.restore();
}

// ═══════════════════════════════════════════════════════
// TAB 4: VELOCITY
// ═══════════════════════════════════════════════════════

async function loadVelocity() {
  try {
    const cached = cacheGet('velocity');
    const data = cached || await apiFetch('/api/velocity/top');
    if (!cached) cacheSet('velocity', data);

    const voids = data.voids || [];

    // Count warming for header chip
    const warmingCount = voids.filter(v => v.classification === 'warming' || v.classification === 'hot').length;
    cacheSet('warming_count', warmingCount);
    setChip('chip-warming', warmingCount);

    // Split by classification
    const hot = voids.filter(v => v.classification === 'hot');
    const warming = voids.filter(v => v.classification === 'warming');
    const cold = voids.filter(v => v.classification === 'cold');

    renderVelocityColumn('velocity-hot', hot, '#ff3366');
    renderVelocityColumn('velocity-warming', warming, '#ff8800');
    renderVelocityColumn('velocity-cold', cold, '#3366ff');
  } catch (err) {
    showToast('Failed to load velocity data', true);
  }
}

function renderVelocityColumn(containerId, voids, accentColor) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (!voids.length) {
    container.innerHTML = '<div class="no-data">No voids in this category.</div>';
    return;
  }

  container.innerHTML = '';
  voids.forEach(v => {
    const card = document.createElement('div');
    card.className = 'velocity-card';

    const papers = [
      v.papers_2018_2020 || 0,
      v.papers_2020_2022 || 0,
      v.papers_2022_2024 || 0,
      v.papers_2024_2026 || 0,
    ];
    const maxPapers = Math.max(...papers, 1);

    const trend = v.velocity_trend || 0;
    const trendArrow = trend > 0.3 ? '&#9650;' : trend < -0.3 ? '&#9660;' : '&#9654;';

    card.innerHTML = `
      <div class="velocity-card-header">
        <span class="velocity-card-id">${v.void_id}</span>
        <span class="velocity-card-score" style="color:${scoreColorFn(v.overall_score || 0)}">${(v.overall_score || 0).toFixed(0)}</span>
      </div>
      <div class="velocity-card-desc">${truncate(v.description || '', 80)}</div>

      <div class="velocity-sparkline">
        ${papers.map(p => {
          const h = Math.max(2, (p / maxPapers) * 30);
          return `<div class="sparkline-bar" style="height:${h}px;background:${accentColor}"></div>`;
        }).join('')}
      </div>
      <div class="sparkline-labels">
        <span>'18-20</span>
        <span>'20-22</span>
        <span>'22-24</span>
        <span>'24-26</span>
      </div>

      <div class="velocity-trend" style="color:${accentColor}">
        ${trendArrow} Trend: ${trend > 0 ? '+' : ''}${trend.toFixed(1)} papers/window
      </div>
      ${v.classification === 'hot' ? '<div class="velocity-urgency">Urgency: MOVE THIS WEEK</div>' : ''}
    `;

    container.appendChild(card);
  });
}

// ═══════════════════════════════════════════════════════
// TAB 5: CUSTOM SCORER
// ═══════════════════════════════════════════════════════

function initScorer() {
  document.getElementById('btn-score-pattern')?.addEventListener('click', scoreCustomPattern);
}

function initScorerPositions() {
  buildScorerPositions('scorer-guide-positions', scorerGuide, 'guide');
  buildScorerPositions('scorer-passenger-positions', scorerPassenger, 'passenger');
  buildScorerRegionLabels();
}

function buildScorerPositions(containerId, mods, strand) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';

  mods.forEach((mod, i) => {
    const pos = document.createElement('div');
    pos.className = 'scorer-pos';
    pos.style.background = modBg(mod);
    pos.style.borderColor = (MOD_COLORS[mod] || '#888') + '40';

    pos.innerHTML = `
      <span class="scorer-pos-num">${i + 1}</span>
      <span class="scorer-pos-mod" style="color:${MOD_COLORS[mod] || '#888'}">${SUGAR_ABBREV[mod] || '?'}</span>
    `;

    pos.addEventListener('click', () => {
      openModPicker(`${strand === 'guide' ? 'Guide' : 'Passenger'} Position ${i + 1}`, mod, (newMod) => {
        if (strand === 'guide') scorerGuide[i] = newMod;
        else scorerPassenger[i] = newMod;
        buildScorerPositions(containerId, strand === 'guide' ? scorerGuide : scorerPassenger, strand);
      });
    });

    container.appendChild(pos);
  });
}

function buildScorerRegionLabels() {
  const container = document.getElementById('scorer-guide-regions');
  if (!container) return;
  container.innerHTML = '';

  for (let i = 1; i <= 21; i++) {
    const marker = document.createElement('div');
    marker.className = 'scorer-region-marker';
    marker.style.width = '48px';
    marker.style.flexShrink = '0';

    if (SEED_RANGE.includes(i)) {
      marker.classList.add('seed');
      marker.textContent = i === 2 ? 'Seed' : '';
    } else if (CLEAVAGE_RANGE.includes(i)) {
      marker.classList.add('cleavage');
      marker.textContent = i === 10 ? 'Cleav' : '';
    } else if (SUPPL_RANGE.includes(i)) {
      marker.classList.add('suppl');
      marker.textContent = i === 13 ? 'Suppl' : '';
    } else if (OVERHANG_RANGE.includes(i)) {
      marker.classList.add('overhang');
      marker.textContent = i === 19 ? '3\'OH' : '';
    }

    container.appendChild(marker);
  }
}

async function scoreCustomPattern() {
  const btn = document.getElementById('btn-score-pattern');
  const resultsEl = document.getElementById('scorer-results');
  const compEl = document.getElementById('scorer-comparison');

  btn.disabled = true;
  btn.textContent = 'Scoring...';
  resultsEl.style.display = 'none';
  compEl.style.display = 'none';

  // Build backbone arrays
  const bbGuideTerm = document.getElementById('scorer-bb-guide-term').value;
  const bbGuideInt = document.getElementById('scorer-bb-guide-int').value;
  const bbPassTerm = document.getElementById('scorer-bb-pass-term').value;
  const bbPassInt = document.getElementById('scorer-bb-pass-int').value;

  const backboneGuide = [];
  const backbonePass = [];
  for (let i = 0; i < 20; i++) {
    const isTerminal = i < 2 || i >= 18;
    backboneGuide.push(isTerminal ? bbGuideTerm : bbGuideInt);
    backbonePass.push(isTerminal ? bbPassTerm : bbPassInt);
  }

  const conjugate = document.getElementById('scorer-conjugate').value;

  try {
    const result = await apiFetch('/api/score/custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        guide_modifications: scorerGuide,
        passenger_modifications: scorerPassenger,
        backbone_guide: backboneGuide,
        backbone_passenger: backbonePass,
        conjugate,
      }),
    });

    renderScorerResults(result, resultsEl);
    resultsEl.style.display = 'block';

    // Compare to nearest known
    renderComparison(result, compEl);
    compEl.style.display = 'block';

    // Animate score bars
    requestAnimationFrame(() => {
      resultsEl.querySelectorAll('.score-bar-fill').forEach(bar => {
        bar.style.width = bar.dataset.width;
      });
    });
  } catch (err) {
    showToast('Scoring failed: ' + err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Score This Pattern';
  }
}

function renderScorerResults(result, container) {
  const overall = result.overall_oligovoid_score || 0;
  const scoreColor = scoreColorFn(overall);

  const bars = [
    { label: 'Thermodynamic', value: result.thermodynamic_score },
    { label: 'RISC Loading', value: result.risc_loading_score },
    { label: 'Nuclease Resistance', value: result.nuclease_resistance_score },
    { label: 'Off-Target Risk', value: result.off_target_risk_score ? (100 - result.off_target_risk_score) : null },
  ];

  container.innerHTML = `
    <h3>Score Results</h3>

    <div style="display:flex;align-items:baseline;gap:1rem;margin-bottom:1rem;">
      <span class="mono" style="font-size:2.2rem;font-weight:700;color:${scoreColor}">${overall.toFixed(1)}</span>
      <span style="color:var(--text-secondary);font-size:0.82rem;">/100 Overall OligoVoid Score</span>
    </div>

    <div class="score-bars">
      ${bars.map(b => {
        if (b.value == null) return '';
        const c = scoreColorFn(b.value);
        const cls = b.value >= 75 ? 'bg-score-high' : b.value >= 50 ? 'bg-score-mid' : 'bg-score-low';
        return `<div class="score-bar-item">
          <div class="score-bar-top">
            <span class="score-bar-label">${b.label}</span>
            <span class="score-bar-value" style="color:${c}">${b.value.toFixed(1)}</span>
          </div>
          <div class="score-bar-track">
            <div class="score-bar-fill ${cls}" data-width="${b.value}%" style="width:0%"></div>
          </div>
        </div>`;
      }).join('')}
    </div>

    ${result.guide_display ? `
    <div style="margin-top:1rem;padding:0.8rem;background:var(--bg);border-radius:var(--radius);font-family:var(--font-mono);font-size:0.7rem;color:var(--text-mono);white-space:pre-wrap;overflow-x:auto;">Guide:     ${result.guide_display}
Passenger: ${result.passenger_display || ''}</div>` : ''}

    ${result.classification ? `
    <div class="void-badges" style="margin-top:0.8rem;">
      <span class="void-badge type-badge">${formatVoidType(result.classification.void_type || '')}</span>
      <span class="void-badge" style="border-color:var(--border-bright);color:var(--text-secondary);">Risk: ${result.classification.exploration_risk || '?'}</span>
      <span class="void-badge" style="border-color:var(--border-bright);color:var(--text-secondary);">Synthesis: ${result.classification.estimated_synthesis_complexity || '?'}</span>
    </div>` : ''}
  `;
}

function renderComparison(result, container) {
  if (!knownPatterns || !knownPatterns.length) {
    container.style.display = 'none';
    return;
  }

  // Find nearest known pattern by Hamming distance
  let nearestId = result.closest_known_pattern_id;
  let nearest = knownPatterns.find(p => p.pattern_id === nearestId);
  if (!nearest) nearest = knownPatterns[0];

  const hamming = result.hamming_distance_to_nearest || '?';

  container.innerHTML = `
    <h4>Compared to Nearest Known: ${nearest.drug_name} (${nearest.pattern_id})</h4>
    <div style="font-size:0.72rem;color:var(--text-secondary);margin-bottom:0.5rem;">
      Hamming distance: <span class="mono color-cyan">${hamming}</span> positions differ
    </div>
    <div style="font-size:0.72rem;margin-bottom:0.3rem;">
      <span style="color:var(--text-secondary);">Known:</span>
      <span class="mono" style="color:var(--text-mono);">${nearest.guide_notation}</span>
      <span style="color:var(--text-secondary);margin-left:0.5rem;">KD: ${nearest.reported_knockdown || '?'}%</span>
    </div>
    <div style="font-size:0.72rem;">
      <span style="color:var(--text-secondary);">Yours:</span>
      <span class="mono" style="color:var(--accent-cyan);">${scorerGuide.map(m => SUGAR_ABBREV[m]).join('')}</span>
    </div>
  `;
}

// ═══════════════════════════════════════════════════════
// MODIFICATION PICKER POPUP
// ═══════════════════════════════════════════════════════

function initModPicker() {
  document.getElementById('mod-picker-close')?.addEventListener('click', closeModPicker);
  document.getElementById('mod-picker-overlay')?.addEventListener('click', (e) => {
    if (e.target.id === 'mod-picker-overlay') closeModPicker();
  });
}

function openModPicker(title, currentMod, callback) {
  const overlay = document.getElementById('mod-picker-overlay');
  const titleEl = document.getElementById('mod-picker-title');
  const optionsEl = document.getElementById('mod-picker-options');

  titleEl.textContent = title;
  pickerCallback = callback;

  optionsEl.innerHTML = SUGAR_MODS.map(mod => {
    const selected = mod === currentMod ? 'selected' : '';
    return `
      <div class="mod-picker-option ${selected}" data-mod="${mod}" onclick="selectMod(this)">
        <span class="mod-picker-dot" style="background:${MOD_COLORS[mod]}"></span>
        <span class="mod-picker-name">${SUGAR_ABBREV[mod]} ${mod}</span>
      </div>
    `;
  }).join('');

  overlay.style.display = 'flex';
}

function selectMod(el) {
  const mod = el.dataset.mod;
  if (pickerCallback) pickerCallback(mod);
  closeModPicker();
}

function closeModPicker() {
  document.getElementById('mod-picker-overlay').style.display = 'none';
  pickerCallback = null;
}

// ═══════════════════════════════════════════════════════
// SCORE CARD (Full, for designer)
// ═══════════════════════════════════════════════════════

function renderScoreCardFull(result, containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const overall = result.overall_oligovoid_score || 0;
  const scoreColor = scoreColorFn(overall);

  container.innerHTML = `
    <h4 style="color:var(--accent-cyan);">Full Analysis</h4>
    <div style="display:flex;align-items:baseline;gap:0.6rem;margin:0.5rem 0;">
      <span class="mono" style="font-size:1.8rem;font-weight:700;color:${scoreColor}">${overall.toFixed(1)}</span>
      <span style="color:var(--text-secondary);font-size:0.75rem;">/100 OligoVoid Score</span>
    </div>
    <div class="score-bars" style="margin:0.6rem 0;">
      ${[
        { label: 'Thermodynamic', val: result.thermodynamic_score },
        { label: 'RISC Loading', val: result.risc_loading_score },
        { label: 'Nuclease Resistance', val: result.nuclease_resistance_score },
        { label: 'Off-Target', val: result.off_target_risk_score ? (100 - result.off_target_risk_score) : null },
      ].map(b => {
        if (b.val == null) return '';
        const cls = b.val >= 75 ? 'bg-score-high' : b.val >= 50 ? 'bg-score-mid' : 'bg-score-low';
        return `<div class="score-bar-item">
          <div class="score-bar-top"><span class="score-bar-label">${b.label}</span><span class="score-bar-value" style="color:${scoreColorFn(b.val)}">${b.val.toFixed(0)}</span></div>
          <div class="score-bar-track"><div class="score-bar-fill ${cls}" style="width:${b.val}%"></div></div>
        </div>`;
      }).join('')}
    </div>
    ${result.classification ? `<div class="void-badges" style="margin-top:0.5rem;"><span class="void-badge type-badge">${formatVoidType(result.classification.void_type || '')}</span></div>` : ''}
  `;
}

// ═══════════════════════════════════════════════════════
// TOAST NOTIFICATIONS
// ═══════════════════════════════════════════════════════

function showToast(msg, isError = false) {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast${isError ? ' error' : ''}`;
  toast.textContent = msg;
  container.appendChild(toast);

  requestAnimationFrame(() => toast.classList.add('show'));

  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ═══════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════

function truncate(str, max) {
  if (str.length <= max) return str;
  return str.slice(0, max) + '...';
}

// Make toggleVoidExpand and selectMod globally accessible
window.toggleVoidExpand = toggleVoidExpand;
window.selectMod = selectMod;
