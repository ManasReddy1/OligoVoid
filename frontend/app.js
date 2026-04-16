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
      if (tab === 'fda') loadFDAValidation();
      if (tab === 'dmtl') loadDMTL();
      if (tab === 'velocity') loadVelocity();
      if (tab === 'scorer') initScorerPositions();
      if (tab === 'generative') initGenerativeTab();
      if (tab === 'casestudy') loadCaseStudy();
      if (tab === 'howworks') {}  // static content, no load needed
      if (tab === 'validation') loadValidation();
      if (tab === 'latent') loadLatentSpace();
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


// ═══════════════════════════════════════════════════════
// TAB 6: AI GENERATED (CVAE + GP)
// ═══════════════════════════════════════════════════════

let generativeInitialized = false;

function initGenerativeTab() {
  if (generativeInitialized) return;
  generativeInitialized = true;

  // Wire up sliders
  const efficacySlider = document.getElementById('gen-efficacy');
  const tempSlider = document.getElementById('gen-temp');
  const countSlider = document.getElementById('gen-count');

  if (efficacySlider) {
    efficacySlider.addEventListener('input', () => {
      document.getElementById('gen-efficacy-value').textContent = efficacySlider.value;
    });
  }
  if (tempSlider) {
    tempSlider.addEventListener('input', () => {
      document.getElementById('gen-temp-value').textContent = parseFloat(tempSlider.value).toFixed(1);
    });
  }
  if (countSlider) {
    countSlider.addEventListener('input', () => {
      document.getElementById('gen-count-value').textContent = countSlider.value;
    });
  }

  // Wire up generate button
  const btn = document.getElementById('btn-generate');
  if (btn) {
    btn.addEventListener('click', runGeneration);
  }
}

async function runGeneration() {
  const efficacy = parseFloat(document.getElementById('gen-efficacy').value);
  const temp = parseFloat(document.getElementById('gen-temp').value);
  const count = parseInt(document.getElementById('gen-count').value);

  const loading = document.getElementById('gen-loading');
  const results = document.getElementById('gen-results');
  const noteEl = document.getElementById('gen-model-note');

  loading.style.display = 'flex';
  results.style.display = 'none';
  noteEl.style.display = 'none';

  try {
    const data = await apiFetch('/api/generate/candidates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_efficacy: efficacy,
        temperature: temp,
        n_generate: count,
      }),
    });

    loading.style.display = 'none';
    renderGeneratedCandidates(data);
  } catch (err) {
    loading.style.display = 'none';
    showToast(`Generation failed: ${err.message}`, true);
  }
}

function renderGeneratedCandidates(data) {
  const results = document.getElementById('gen-results');
  const cardsEl = document.getElementById('gen-cards');
  const noteEl = document.getElementById('gen-model-note');

  results.style.display = 'block';

  if (!data.candidates || data.candidates.length === 0) {
    cardsEl.innerHTML = '<div class="no-data">No valid candidates generated. Try adjusting temperature.</div>';
    return;
  }

  cardsEl.innerHTML = data.candidates.map((cand, idx) => {
    const pred = cand.predicted_efficacy || 0;
    const unc = cand.uncertainty_std || 0;
    const conf = cand.model_confidence || 'low';
    const confClass = conf === 'high' ? 'high' : conf === 'medium' ? 'medium' : 'low';
    const isNovel = cand.is_novel;

    // Generate fake pattern blocks for visualization (feature-vector based)
    const patternHtml = renderFeatureBlocks(cand.feature_vector_original || []);

    return `
      <div class="gen-card">
        <div class="gen-card-header">
          <span class="gen-card-rank">#${cand.rank || idx + 1}</span>
          ${isNovel
            ? '<span class="gen-card-badge novel">Novel</span>'
            : '<span class="gen-card-badge void">Near Known</span>'}
        </div>
        <div class="gen-card-pattern">${patternHtml}</div>
        <div class="gen-card-stats">
          <div class="gen-stat">
            <span class="gen-stat-label">Predicted efficacy</span>
            <span class="gen-stat-value ${confClass}">${pred.toFixed(0)}% knockdown</span>
          </div>
          <div class="gen-stat">
            <span class="gen-stat-label">Uncertainty</span>
            <span class="gen-stat-value">&plusmn;${unc.toFixed(0)}% (${conf} confidence)</span>
          </div>
          <div class="gen-stat">
            <span class="gen-stat-label">Extrapolation</span>
            <span class="gen-stat-value">${cand.is_extrapolation ? 'Yes — novel chemistry' : 'No — within training range'}</span>
          </div>
          <div class="gen-stat">
            <span class="gen-stat-label">Target</span>
            <span class="gen-stat-value">${cand.target_efficacy_pct}% at temp ${cand.temperature}</span>
          </div>
        </div>
      </div>
    `;
  }).join('');

  // Model note
  if (data.gp_model_note) {
    noteEl.textContent = data.gp_model_note;
    noteEl.style.display = 'block';
  }
}

function renderFeatureBlocks(features) {
  // Visualize the first 21 features as colored blocks (representing guide-strand-like profile)
  const colors = ['#3b82f6', '#22c55e', '#ef4444', '#f97316', '#a78bfa', '#8892b0', '#ec4899', '#f59e0b'];
  const blocks = [];
  const nBlocks = Math.min(21, features.length);
  for (let i = 0; i < nBlocks; i++) {
    const val = features[i] || 0;
    // Map feature value to color intensity
    const absVal = Math.min(Math.abs(val), 3);
    const colorIdx = Math.floor((absVal / 3) * (colors.length - 1));
    const color = colors[Math.min(colorIdx, colors.length - 1)];
    const opacity = 0.4 + (absVal / 3) * 0.6;
    blocks.push(
      `<div class="gen-mod-block" style="background:${color};opacity:${opacity.toFixed(2)}" title="Feature ${i+1}: ${val.toFixed(2)}"></div>`
    );
  }
  // Pad to 21 if fewer
  for (let i = nBlocks; i < 21; i++) {
    blocks.push('<div class="gen-mod-block" style="background:#8892b0;opacity:0.3"></div>');
  }
  return blocks.join('');
}


// ═══════════════════════════════════════════════════════
// TAB 7: MODEL VALIDATION
// ═══════════════════════════════════════════════════════

let validationData = null;

async function loadValidation() {
  if (validationData) return; // already loaded

  const loading = document.getElementById('val-loading');
  loading.style.display = 'flex';

  try {
    validationData = await apiFetch('/api/model/validation');
    loading.style.display = 'none';
    renderValidation(validationData);
  } catch (err) {
    loading.style.display = 'none';
    showToast(`Failed to load validation data: ${err.message}`, true);
  }
}

function renderValidation(data) {
  // Section 1: Training Data Table
  const tableWrap = document.getElementById('val-training-table');
  if (data.training_data && data.training_data.datasets) {
    const ds = data.training_data.datasets;
    tableWrap.innerHTML = `
      <table class="val-table">
        <thead>
          <tr><th>Dataset</th><th>N sequences</th><th>Cell Line</th><th>Year</th><th>Citation</th></tr>
        </thead>
        <tbody>
          ${ds.map(d => `
            <tr>
              <td>${d.dataset}</td>
              <td style="font-family:var(--font-mono)">${(d.n_sequences || 0).toLocaleString()}</td>
              <td>${d.cell_line}</td>
              <td>${d.year}</td>
              <td style="font-size:0.65rem;color:var(--text-secondary)">${d.citation}</td>
            </tr>
          `).join('')}
          <tr style="font-weight:700;border-top:2px solid var(--border-bright)">
            <td>Total</td>
            <td style="font-family:var(--font-mono)">${(data.training_data.total_sequences || 0).toLocaleString()}</td>
            <td colspan="3"></td>
          </tr>
        </tbody>
      </table>
    `;
  }

  // Section 2: Cross-Validation Metrics
  const cvEl = document.getElementById('val-cv-metrics');
  const cv = data.cross_validation || {};
  if (cv.cv_pearson_r != null) {
    cvEl.innerHTML = `
      <div class="val-metric-card">
        <div class="val-metric-value">${cv.cv_pearson_r.toFixed(3)}</div>
        <div class="val-metric-label">Pearson r</div>
      </div>
      <div class="val-metric-card">
        <div class="val-metric-value">${cv.cv_rmse.toFixed(1)}%</div>
        <div class="val-metric-label">RMSE</div>
      </div>
      <div class="val-metric-card">
        <div class="val-metric-value">${cv.cv_r2.toFixed(3)}</div>
        <div class="val-metric-label">R&sup2;</div>
      </div>
      <div class="val-metric-card">
        <div class="val-metric-value">${cv.n_train || 0}</div>
        <div class="val-metric-label">Train (subsampled)</div>
      </div>
      <div class="val-metric-card">
        <div class="val-metric-value">${(cv.n_total || 0).toLocaleString()}</div>
        <div class="val-metric-label">Total sequences</div>
      </div>
    `;

    const r = cv.cv_pearson_r;
    const varianceExplained = (r * r * 100).toFixed(1);
    document.getElementById('val-cv-explanation').innerHTML =
      `A Pearson r of ${r.toFixed(3)} means our model explains ~${varianceExplained}% of the variation in knockdown efficacy. ` +
      `This is modest — intentionally so. Our GP prioritizes <strong>calibrated uncertainty</strong> over raw prediction accuracy. ` +
      `The model honestly reports when it doesn't know, which is more valuable for experiment prioritization than a high r that overfits.`;
  } else {
    cvEl.innerHTML = '<div class="no-data">GP model not yet trained. Start the server to auto-train.</div>';
  }

  // Section 3: FDA Drug Validation
  const fdaEl = document.getElementById('val-fda-table');
  const fdaSummaryEl = document.getElementById('val-fda-summary');
  const fda = data.fda_validation || {};

  if (fda.predictions && fda.predictions.length > 0) {
    fdaEl.innerHTML = `
      <table class="val-table">
        <thead>
          <tr><th>Drug</th><th>Real Efficacy</th><th>Our Prediction</th><th>Error</th><th>Status</th></tr>
        </thead>
        <tbody>
          ${fda.predictions.map(p => {
            const error = Math.abs((p.actual || 0) - (p.predicted || 0));
            const light = error < 15 ? 'green' : error < 30 ? 'yellow' : 'red';
            return `
              <tr>
                <td>${p.drug || p.pattern_id || '—'}</td>
                <td style="font-family:var(--font-mono)">${(p.actual || 0).toFixed(0)}%</td>
                <td style="font-family:var(--font-mono)">${(p.predicted || 0).toFixed(0)}%</td>
                <td style="font-family:var(--font-mono)">${error.toFixed(0)}%</td>
                <td><span class="traffic-light ${light}"></span></td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    `;

    const mae = fda.mae != null ? fda.mae.toFixed(1) : '?';
    const nCorrect = fda.n_correct_high || 0;
    const nDrugs = fda.n_drugs || fda.predictions.length;
    fdaSummaryEl.innerHTML =
      `We correctly identify <strong>${nCorrect} of ${nDrugs}</strong> FDA drugs as efficacious, ` +
      `with an average prediction error of <strong>${mae}%</strong>. ` +
      `The GP was trained on unmodified RNA sequences — predicting modified drug patterns is extrapolation, ` +
      `so high uncertainty is expected and <em>honest</em>.`;
  } else {
    fdaEl.innerHTML = '<div class="no-data">FDA validation not yet available. Train the GP model first.</div>';
  }
}


/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   TAB 8: LATENT SPACE
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

let latentLoaded = false;

function loadLatentSpace() {
  if (latentLoaded) return;

  const loading = document.getElementById('latent-loading');
  if (loading) loading.style.display = 'flex';

  // Load map + dimensions in parallel
  Promise.all([
    fetch(`${API}/api/latent/map`).then(r => r.json()),
    fetch(`${API}/api/latent/dimensions`).then(r => r.json()),
  ])
    .then(([mapData, dimData]) => {
      if (loading) loading.style.display = 'none';
      if (!mapData.error) renderLatentScatter(mapData);
      if (!dimData.error) renderLatentDimensions(dimData);
      latentLoaded = true;
    })
    .catch(err => {
      if (loading) loading.style.display = 'none';
      console.error('Latent space load error:', err);
      document.getElementById('latent-cluster-summary').textContent =
        'Failed to load latent space data. Is the CVAE model trained?';
    });

  // Wire up interpolation button
  const btn = document.getElementById('btn-interpolate');
  if (btn) {
    btn.addEventListener('click', runInterpolation);
  }
}

function renderLatentScatter(data) {
  const canvas = document.getElementById('latent-scatter-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;
  const pad = 50;

  // Gather all points for bounds
  const allPts = [
    ...data.known_patterns.map(p => ({ ...p, type: 'known' })),
    ...data.void_candidates.map(p => ({ ...p, type: 'void' })),
  ];

  if (allPts.length === 0) {
    ctx.fillStyle = '#8892b0';
    ctx.font = '14px Inter, sans-serif';
    ctx.fillText('No data points to display.', W / 2 - 80, H / 2);
    return;
  }

  const xs = allPts.map(p => p.x);
  const ys = allPts.map(p => p.y);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const xRange = (xMax - xMin) || 1;
  const yRange = (yMax - yMin) || 1;

  const toCanvasX = x => pad + ((x - xMin) / xRange) * (W - 2 * pad);
  const toCanvasY = y => H - pad - ((y - yMin) / yRange) * (H - 2 * pad);

  // Clear
  ctx.clearRect(0, 0, W, H);

  // Background grid
  ctx.strokeStyle = '#1e2840';
  ctx.lineWidth = 0.5;
  for (let i = 0; i <= 5; i++) {
    const gx = pad + (i / 5) * (W - 2 * pad);
    const gy = pad + (i / 5) * (H - 2 * pad);
    ctx.beginPath(); ctx.moveTo(gx, pad); ctx.lineTo(gx, H - pad); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(pad, gy); ctx.lineTo(W - pad, gy); ctx.stroke();
  }

  // Axes labels
  ctx.fillStyle = '#8892b0';
  ctx.font = '11px Inter, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('Latent Dimension 1', W / 2, H - 10);
  ctx.save();
  ctx.translate(14, H / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText('Latent Dimension 2', 0, 0);
  ctx.restore();

  // Draw void points first (behind known)
  data.void_candidates.forEach(p => {
    const cx = toCanvasX(p.x);
    const cy = toCanvasY(p.y);
    const size = 5;
    ctx.fillStyle = p.category === 'high_score_void' ? '#00d4ff' : '#64748b';
    ctx.globalAlpha = 0.7;
    // Diamond shape for voids
    ctx.beginPath();
    ctx.moveTo(cx, cy - size);
    ctx.lineTo(cx + size, cy);
    ctx.lineTo(cx, cy + size);
    ctx.lineTo(cx - size, cy);
    ctx.closePath();
    ctx.fill();
  });

  ctx.globalAlpha = 1.0;

  // Draw known patterns
  data.known_patterns.forEach(p => {
    const cx = toCanvasX(p.x);
    const cy = toCanvasY(p.y);

    if (p.category === 'fda_drug') {
      // Gold star
      drawStar(ctx, cx, cy, 8, 5, '#fbbf24');
      // Label
      if (p.drug_name) {
        ctx.fillStyle = '#fbbf24';
        ctx.font = 'bold 9px Inter, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(p.drug_name, cx + 10, cy + 3);
      }
    } else {
      const colors = {
        high_efficacy: '#22c55e',
        medium_efficacy: '#3b82f6',
        low_efficacy: '#ef4444',
      };
      const r = p.category === 'high_efficacy' ? 5 : 4;
      ctx.fillStyle = colors[p.category] || '#3b82f6';
      ctx.globalAlpha = 0.8;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1.0;
    }
  });

  // Summary
  const summaryEl = document.getElementById('latent-cluster-summary');
  if (summaryEl) summaryEl.textContent = data.cluster_summary || '';

  const interpEl = document.getElementById('latent-interpretation');
  if (interpEl) interpEl.textContent = data.interpretation || '';
}

function drawStar(ctx, cx, cy, outerR, points, color) {
  const innerR = outerR * 0.45;
  ctx.fillStyle = color;
  ctx.beginPath();
  for (let i = 0; i < points * 2; i++) {
    const angle = (i * Math.PI) / points - Math.PI / 2;
    const r = i % 2 === 0 ? outerR : innerR;
    const x = cx + Math.cos(angle) * r;
    const y = cy + Math.sin(angle) * r;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.fill();
}

function runInterpolation() {
  const drugA = document.getElementById('interp-drug-a').value;
  const drugB = document.getElementById('interp-drug-b').value;
  const resultsEl = document.getElementById('latent-interp-results');
  const interpEl = document.getElementById('latent-interp-interpretation');

  if (drugA === drugB) {
    resultsEl.innerHTML = '<div class="no-data">Select two different drugs to interpolate between.</div>';
    return;
  }

  resultsEl.innerHTML = '<div class="latent-loading" style="display:flex"><div class="spinner"></div><span>Interpolating...</span></div>';

  fetch(`${API}/api/latent/interpolation?drug_a=${drugA}&drug_b=${drugB}&n_steps=7`)
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        resultsEl.innerHTML = `<div class="no-data">${data.error}</div>`;
        return;
      }
      renderInterpolation(data, resultsEl, interpEl);
    })
    .catch(err => {
      resultsEl.innerHTML = `<div class="no-data">Interpolation failed: ${err.message}</div>`;
    });
}

function renderInterpolation(data, resultsEl, interpEl) {
  let html = '<div class="latent-interp-steps">';

  data.steps.forEach((step, i) => {
    const isEndpoint = i === 0 || i === data.steps.length - 1;
    const classes = [
      'interp-card',
      isEndpoint ? 'is-endpoint' : '',
      step.is_best_novel ? 'is-best-novel' : '',
    ].filter(Boolean).join(' ');

    const eff = step.predicted_efficacy;
    const effColor = eff >= 80 ? '#22c55e' : eff >= 60 ? '#fbbf24' : '#ef4444';

    html += `<div class="${classes}">`;
    if (step.drug_label) {
      html += `<div class="interp-drug-label">${step.drug_label}</div>`;
    } else {
      html += `<div style="font-size:0.7rem;color:var(--text-secondary)">Step ${step.step}</div>`;
    }
    html += `<div class="interp-eff-value" style="color:${effColor}">${eff}%</div>`;
    html += `<div class="interp-eff-bar"><div class="interp-eff-fill" style="width:${eff}%;background:${effColor}"></div></div>`;
    html += `<div class="interp-notation">${step.pattern_notation}</div>`;
    html += '<div class="interp-badges">';
    if (step.is_novel) html += '<span class="interp-badge interp-badge-novel">NOVEL</span>';
    if (step.is_valid) html += '<span class="interp-badge interp-badge-valid">VALID</span>';
    html += '</div>';
    html += '</div>';
  });

  html += '</div>';
  resultsEl.innerHTML = html;

  if (interpEl) {
    interpEl.textContent = data.interpretation || '';
  }
}

function renderLatentDimensions(data) {
  const container = document.getElementById('latent-dims');
  if (!container || !data.dimensions) return;

  let html = '<div class="latent-dims-grid">';

  data.dimensions.forEach(dim => {
    html += `<div class="latent-dim-card">`;
    html += `<div class="latent-dim-header">`;
    html += `<span class="latent-dim-number">DIM ${dim.dimension}</span>`;
    html += `<span class="latent-dim-group">${dim.dominant_group.replace(/_/g, ' ')}</span>`;
    html += `</div>`;

    // Extremes
    html += `<div class="latent-dim-extremes">`;
    html += `<div class="latent-extreme latent-extreme-pos">`;
    html += `<div class="latent-extreme-label">+ Positive</div>`;
    html += `<div class="latent-extreme-notation">${dim.positive_extreme.pattern_notation}</div>`;
    html += `</div>`;
    html += `<div class="latent-dim-arrow">&harr;</div>`;
    html += `<div class="latent-extreme latent-extreme-neg">`;
    html += `<div class="latent-extreme-label">- Negative</div>`;
    html += `<div class="latent-extreme-notation">${dim.negative_extreme.pattern_notation}</div>`;
    html += `</div>`;
    html += `</div>`;

    // Interpretation
    html += `<div class="latent-dim-interp">${dim.interpretation}</div>`;
    html += `</div>`;
  });

  html += '</div>';

  // Add overall interpretation
  html += `<div class="latent-interpretation" style="margin-top:1rem">${data.interpretation}</div>`;

  container.innerHTML = html;
}


// ═══════════════════════════════════════════════════════
// ONBOARDING MODAL
// ═══════════════════════════════════════════════════════

(function initOnboarding() {
  if (localStorage.getItem('oligovoid_onboarded')) return;
  const overlay = document.getElementById('onboarding-overlay');
  if (!overlay) return;
  overlay.style.display = 'flex';
  let step = 1;

  function showStep(n) {
    step = n;
    overlay.querySelectorAll('.onboarding-step').forEach(s => s.classList.remove('active'));
    overlay.querySelectorAll('.onboarding-dot').forEach(d => d.classList.remove('active'));
    const stepEl = overlay.querySelector(`.onboarding-step[data-step="${n}"]`);
    const dotEl = overlay.querySelector(`.onboarding-dot[data-dot="${n}"]`);
    if (stepEl) stepEl.classList.add('active');
    if (dotEl) dotEl.classList.add('active');
    const btn = document.getElementById('onboarding-next');
    if (btn) btn.textContent = n >= 4 ? 'Got it' : 'Next';
  }

  document.getElementById('onboarding-next')?.addEventListener('click', () => {
    if (step >= 4) {
      overlay.style.display = 'none';
      localStorage.setItem('oligovoid_onboarded', '1');
    } else {
      showStep(step + 1);
    }
  });

  document.getElementById('onboarding-skip')?.addEventListener('click', () => {
    overlay.style.display = 'none';
    localStorage.setItem('oligovoid_onboarded', '1');
  });

  overlay.querySelectorAll('.onboarding-dot').forEach(dot => {
    dot.addEventListener('click', () => {
      const n = parseInt(dot.dataset.dot);
      if (n) showStep(n);
    });
  });
})();


// ═══════════════════════════════════════════════════════
// FDA VALIDATION TAB
// ═══════════════════════════════════════════════════════

let fdaLoaded = false;

async function loadFDAValidation() {
  if (fdaLoaded) return;
  const loading = document.getElementById('fda-loading');
  if (loading) loading.style.display = 'flex';

  try {
    const data = await apiFetch('/api/validation/fda');
    renderFDACards(data.predictions || []);
    renderFDASummary(data.summary || {});
    fdaLoaded = true;
  } catch (err) {
    showToast('Failed to load FDA validation: ' + err.message, true);
  } finally {
    if (loading) loading.style.display = 'none';
  }
}

function renderFDACards(predictions) {
  const container = document.getElementById('fda-drug-cards');
  if (!container) return;

  container.innerHTML = predictions.map(p => {
    const lightClass = 'traffic-' + p.traffic_light;
    const icon = p.direction_correct ? '&#x2713;' : '&#x26a0;&#xfe0f;';
    const clinical = p.clinical_efficacy_pct || 0;
    const predicted = p.biophysics_score || 0;

    return `
      <div class="fda-drug-card ${lightClass}">
        <div class="fda-drug-header">
          <div>
            <div class="fda-drug-name">${p.drug} (${p.brand})</div>
            <div class="fda-drug-meta">Treats: ${p.target} | Approved: ${p.year_approved} | ${p.conjugate}</div>
          </div>
        </div>
        <div class="fda-bar-row">
          <span class="fda-bar-label">Clinical result:</span>
          <div class="fda-bar-track"><div class="fda-bar-fill clinical" style="width:${clinical}%"></div></div>
          <span class="fda-bar-value">${clinical}%</span>
        </div>
        <div class="fda-bar-row">
          <span class="fda-bar-label">OligoVoid score:</span>
          <div class="fda-bar-track"><div class="fda-bar-fill predicted" style="width:${predicted}%"></div></div>
          <span class="fda-bar-value">${predicted}%</span>
        </div>
        <div class="fda-drug-verdict">
          <span class="verdict-icon">${icon}</span>
          ${p.direction_correct ? 'Correctly identified as high-efficacy drug' : 'Classification did not match'}
          ${p.error_pct != null ? ` | Error: ${p.error_pct}%` : ''}
          <br><br>${p.plain_english || ''}
        </div>
      </div>
    `;
  }).join('');
}

function renderFDASummary(summary) {
  const statsEl = document.getElementById('fda-summary-stats');
  const interpEl = document.getElementById('fda-summary-interpretation');
  if (!statsEl || !interpEl) return;

  statsEl.innerHTML = `
    <div class="fda-stat">
      <span class="fda-stat-value">${summary.drugs_correctly_classified_high || '?'}/5</span>
      <span class="fda-stat-label">Correctly Identified</span>
    </div>
    <div class="fda-stat">
      <span class="fda-stat-value">${summary.ranking_spearman || '?'}</span>
      <span class="fda-stat-label">Spearman &rho;</span>
    </div>
    <div class="fda-stat">
      <span class="fda-stat-value">${summary.mean_absolute_error || '?'}%</span>
      <span class="fda-stat-label">Mean Absolute Error</span>
    </div>
  `;

  interpEl.innerHTML = `
    <p><strong>What this means:</strong> A random model would correctly identify ~2-3 of 5 drugs by chance.
    OligoVoid identifies ${summary.drugs_correctly_classified_high || '?'}/5,
    suggesting the scoring system captures real chemical signals from the training data.</p>
    <p style="margin-top:0.5rem;font-style:italic;font-size:0.85rem">${summary.honest_interpretation || ''}</p>
  `;
}


// ═══════════════════════════════════════════════════════
// CASE STUDY TAB
// ═══════════════════════════════════════════════════════

let caseStudyLoaded = false;

async function loadCaseStudy() {
  if (caseStudyLoaded) return;
  const loading = document.getElementById('case-loading');
  if (loading) loading.style.display = 'flex';

  try {
    const data = await apiFetch('/api/casestudy');
    renderCaseStudy(data);
    caseStudyLoaded = true;
  } catch (err) {
    showToast('Failed to load case study: ' + err.message, true);
  } finally {
    if (loading) loading.style.display = 'none';
  }
}

function renderCaseStudy(data) {
  // Executive summary
  const exec = document.getElementById('case-executive');
  if (exec) {
    exec.innerHTML = `
      <div style="font-size:0.8rem;color:var(--accent-biolum);font-family:var(--font-mono);margin-bottom:0.5rem">
        OLIGOVOID SCORE: ${data.overall_oligovoid_score || '?'}/100
        &mdash; Recommendation: ${data.overall_recommendation || '?'}
      </div>
      <p>${data.executive_summary || ''}</p>
    `;
  }

  // What's different
  const diffEl = document.getElementById('case-difference-content');
  if (diffEl) diffEl.innerHTML = `<p>${data.what_is_different || ''}</p>`;

  // Risk assessment
  const riskEl = document.getElementById('case-risk-cards');
  if (riskEl && data.risk_assessment) {
    riskEl.innerHTML = data.risk_assessment.map(r => {
      const cls = r.traffic_light === 'green' ? 'risk-green' : r.traffic_light === 'yellow' ? 'risk-yellow' : 'risk-red';
      const icon = r.traffic_light === 'green' ? '&#x1f7e2;' : r.traffic_light === 'yellow' ? '&#x1f7e1;' : '&#x1f534;';
      return `
        <div class="case-risk-card ${cls}">
          <div class="case-risk-dim">${icon} ${r.dimension} <span class="case-risk-score">${r.score}/100 &mdash; ${r.adjective}</span></div>
          <div class="case-risk-plain">${r.plain_english}</div>
        </div>
      `;
    }).join('');
  }

  // Hypothesis
  const hypEl = document.getElementById('case-hypothesis-content');
  if (hypEl && data.hypothesis) {
    hypEl.innerHTML = `
      <p><strong>If it works:</strong> ${data.hypothesis.if_it_works}</p>
      <p><strong>If it fails:</strong> ${data.hypothesis.if_it_fails}</p>
      <p style="margin-top:0.5rem"><strong>Fastest experiment:</strong> ${data.hypothesis.fastest_experiment}</p>
    `;
  }

  // Closest FDA drug
  const closestEl = document.getElementById('case-closest-content');
  if (closestEl && data.closest_fda_drug) {
    const c = data.closest_fda_drug;
    closestEl.innerHTML = `
      <p>The most similar FDA-approved drug is <strong>${c.drug_name}</strong> (${c.brand || ''}).</p>
      <p>Similarity: ${c.similarity_positions}/${c.total_positions} positions identical (${c.similarity_pct}%).</p>
      <p>Their clinical efficacy: ${c.their_efficacy}%.</p>
      <p>Estimated probability this void achieves &gt;70%: <strong>${c.estimated_success_probability}%</strong></p>
      <p style="font-size:0.85rem;color:var(--text-secondary);margin-top:0.5rem">${c.probability_basis}</p>
    `;
  }

  // Recommendation
  const recEl = document.getElementById('case-recommendation');
  if (recEl) {
    const recClass = data.overall_recommendation === 'PRIORITIZE' ? 'case-rec-prioritize'
      : data.overall_recommendation === 'INVESTIGATE' ? 'case-rec-investigate' : 'case-rec-low';
    recEl.className = 'case-recommendation ' + recClass;
    recEl.innerHTML = `
      <h3>Recommendation: ${data.overall_recommendation || '?'}</h3>
      <p>${data.recommendation_plain_english || ''}</p>
    `;
  }
}
