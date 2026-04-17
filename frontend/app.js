/**
 * OligoVoid — siRNA Chemical Modification Gap Intelligence
 * Frontend application. Pure vanilla JS. No external dependencies.
 * Author: Manas Reddy
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

// Regions (1-indexed)
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
    const item = JSON.parse(localStorage.getItem('ov_' + key));
    if (item && Date.now() - item.ts < CACHE_TTL) return item.data;
  } catch (e) { /* ignore */ }
  return null;
}

function cacheSet(key, data) {
  try {
    localStorage.setItem('ov_' + key, JSON.stringify({ ts: Date.now(), data: data }));
  } catch (e) { /* ignore */ }
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

// Track which tabs have been visited (for explainer boxes)
const visitedTabs = {};

// Track which tabs have loaded data
let fdaLoaded = false;
let caseStudyLoaded = false;
let generativeInitialized = false;
let latentLoaded = false;
let validationData = null;

// Achievement tracking
const achievements = {
  explorer: { id: 'explorer', label: 'Explorer', desc: 'Viewed the dark matter map', unlocked: false },
  scorer: { id: 'scorer', label: 'Scorer', desc: 'Scored a custom pattern', unlocked: false },
  generator: { id: 'generator', label: 'Generator', desc: 'Generated AI candidates', unlocked: false },
  fda: { id: 'fda', label: 'FDA Check', desc: 'Viewed FDA validation', unlocked: false },
  dmtl: { id: 'dmtl', label: 'Simulator', desc: 'Ran a DMTL simulation', unlocked: false },
};

// ═══════════════════════════════════════════════════════
// API HELPERS
// ═══════════════════════════════════════════════════════

async function apiFetch(path, opts) {
  if (!opts) opts = {};
  const resp = await fetch(API + path, opts);
  if (!resp.ok) {
    const err = await resp.json().catch(function() { return { detail: resp.statusText }; });
    throw new Error(err.detail || 'HTTP ' + resp.status);
  }
  return resp.json();
}

// ═══════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', async function() {
  initOnboarding();
  initNav();
  initFilterListeners();
  initDesigner();
  initScorer();
  initModPicker();
  initDMTLControls();
  initExplainerBoxes();
  initTooltips();
  initAchievements();
  initLiveScoring();

  // Load initial data in parallel
  await Promise.all([
    loadStats(),
    loadOntology(),
  ]);

  // Update progress bar and achievements from stats
  updateProgressBar();
  unlockAchievement('explorer');

  // Load first tab
  loadModificationMap();

  // Auto-refresh stats every 60s
  setInterval(loadStats, 60000);
});

// ═══════════════════════════════════════════════════════
// ONBOARDING (5 steps)
// ═══════════════════════════════════════════════════════

function initOnboarding() {
  if (localStorage.getItem('oligovoid_visited')) return;
  var overlay = document.getElementById('onboarding-overlay');
  if (!overlay) return;
  overlay.style.display = 'flex';
  var step = 1;
  var totalSteps = 5;

  function showStep(n) {
    step = n;
    overlay.querySelectorAll('.onboarding-step').forEach(function(s) { s.classList.remove('active'); });
    overlay.querySelectorAll('.onboarding-dot').forEach(function(d) { d.classList.remove('active'); });
    var stepEl = overlay.querySelector('.onboarding-step[data-step="' + n + '"]');
    var dotEl = overlay.querySelector('.onboarding-dot[data-dot="' + n + '"]');
    if (stepEl) stepEl.classList.add('active');
    if (dotEl) dotEl.classList.add('active');
    var btn = document.getElementById('onboarding-next');
    if (btn) btn.textContent = n >= totalSteps ? 'Got it' : 'Next';
    // Hide next/skip buttons on step 5 (has its own Start button)
    var navBtns = document.querySelector('.onboarding-buttons');
    if (navBtns) navBtns.style.display = n >= totalSteps ? 'none' : 'flex';
  }

  function closeOnboarding() {
    overlay.style.display = 'none';
    localStorage.setItem('oligovoid_visited', '1');
  }

  var nextBtn = document.getElementById('onboarding-next');
  if (nextBtn) {
    nextBtn.addEventListener('click', function() {
      if (step >= totalSteps) {
        closeOnboarding();
      } else {
        showStep(step + 1);
      }
    });
  }

  var skipBtn = document.getElementById('onboarding-skip');
  if (skipBtn) {
    skipBtn.addEventListener('click', closeOnboarding);
  }

  var startBtn = document.getElementById('onboarding-start');
  if (startBtn) {
    startBtn.addEventListener('click', closeOnboarding);
  }

  overlay.querySelectorAll('.onboarding-dot').forEach(function(dot) {
    dot.addEventListener('click', function() {
      var n = parseInt(dot.dataset.dot);
      if (n) showStep(n);
    });
  });
}

// ═══════════════════════════════════════════════════════
// EXPLAINER BOXES (collapsible "What am I looking at?")
// ═══════════════════════════════════════════════════════

function initExplainerBoxes() {
  document.querySelectorAll('.explainer-collapsible').forEach(function(box) {
    var toggle = box.querySelector('.explainer-toggle');
    var tabKey = box.dataset.tabKey;
    if (toggle) {
      toggle.addEventListener('click', function() {
        box.classList.toggle('collapsed');
        // Remember collapse state
        if (tabKey) {
          localStorage.setItem('ov_explainer_' + tabKey, box.classList.contains('collapsed') ? '1' : '0');
        }
      });
    }
    // On first visit, explainer is open. On return visits, collapse it.
    if (tabKey) {
      var stored = localStorage.getItem('ov_explainer_' + tabKey);
      if (stored === '1') {
        box.classList.add('collapsed');
      }
      // else: default open (first visit)
    }
  });
}

// ═══════════════════════════════════════════════════════
// TOOLTIP SYSTEM (data-tooltip attributes)
// ═══════════════════════════════════════════════════════

function initTooltips() {
  var tooltip = document.getElementById('number-tooltip');
  if (!tooltip) return;

  document.addEventListener('mouseover', function(e) {
    var target = e.target.closest('[data-tooltip]');
    if (target) {
      tooltip.textContent = target.dataset.tooltip;
      tooltip.style.display = 'block';
      positionElement(tooltip, e);
    }
  });

  document.addEventListener('mouseout', function(e) {
    var target = e.target.closest('[data-tooltip]');
    if (target) {
      tooltip.style.display = 'none';
    }
  });

  document.addEventListener('mousemove', function(e) {
    if (tooltip.style.display === 'block') {
      positionElement(tooltip, e);
    }
  });
}

function positionElement(el, e) {
  var x = e.clientX + 12;
  var y = e.clientY + 12;
  el.style.left = Math.min(x, window.innerWidth - 280) + 'px';
  el.style.top = Math.min(y, window.innerHeight - 80) + 'px';
}

// ═══════════════════════════════════════════════════════
// NAVIGATION (9 tabs)
// ═══════════════════════════════════════════════════════

function initNav() {
  document.querySelectorAll('.nav-tab').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var tab = btn.dataset.tab;
      document.querySelectorAll('.nav-tab').forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');

      document.querySelectorAll('.tab-panel').forEach(function(p) {
        p.classList.remove('active');
      });

      var panel = document.getElementById('tab-' + tab);
      if (panel) {
        panel.classList.add('active');
        void panel.offsetWidth; // reflow for CSS transition
      }

      // Mark as visited for explainer collapse on next visit
      if (!visitedTabs[tab]) {
        visitedTabs[tab] = true;
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
      if (tab === 'howworks') { /* static content */ }
    });
  });
}

// ═══════════════════════════════════════════════════════
// STATS (Header chips)
// ═══════════════════════════════════════════════════════

async function loadStats() {
  try {
    var cached = cacheGet('stats');
    statsData = cached || await apiFetch('/api/stats');
    if (!cached) cacheSet('stats', statsData);
    renderHeaderChips();
  } catch (err) {
    showToast('Failed to load stats', true);
  }
}

function renderHeaderChips() {
  if (!statsData) return;
  var s = statsData;
  setChip('chip-explored', (s.modification_space_explored_pct || 0) + '%');
  setChip('chip-voids', s.total_void_candidates || 0);
  setChip('chip-fda', s.fda_drugs_validated || 5);
  setChip('chip-generated', s.total_generated || 0);
  updateProgressBar();
}

function setChip(id, value) {
  var chip = document.getElementById(id);
  if (chip) chip.querySelector('.chip-value').textContent = value;
}

// ═══════════════════════════════════════════════════════
// PROGRESS BAR + ACHIEVEMENTS
// ═══════════════════════════════════════════════════════

function updateProgressBar() {
  if (!statsData) return;
  var pct = statsData.modification_space_explored_pct || 0;
  var fill = document.getElementById('progress-bar-fill');
  var label = document.getElementById('progress-label');
  if (fill) {
    requestAnimationFrame(function() { fill.style.width = pct + '%'; });
  }
  if (label) {
    var voids = statsData.total_void_candidates || 0;
    label.innerHTML = '<strong>' + pct + '%</strong> of modification space explored | <strong>' + voids + '</strong> voids ranked';
  }
}

function initAchievements() {
  // Load saved achievements
  try {
    var saved = JSON.parse(localStorage.getItem('ov_achievements') || '{}');
    Object.keys(saved).forEach(function(key) {
      if (achievements[key]) achievements[key].unlocked = saved[key];
    });
  } catch (e) { /* ignore */ }
  renderAchievements();
}

function renderAchievements() {
  var row = document.getElementById('achievement-row');
  if (!row) return;
  row.innerHTML = Object.values(achievements).map(function(a) {
    var cls = 'achievement-badge badge-' + a.id;
    if (a.unlocked) cls += ' unlocked';
    else cls += ' locked';
    return '<span class="' + cls + '" title="' + a.desc + '">' + a.label + '</span>';
  }).join('');
}

function unlockAchievement(key) {
  if (!achievements[key] || achievements[key].unlocked) return;
  achievements[key].unlocked = true;
  try {
    var saved = JSON.parse(localStorage.getItem('ov_achievements') || '{}');
    saved[key] = true;
    localStorage.setItem('ov_achievements', JSON.stringify(saved));
  } catch (e) { /* ignore */ }
  renderAchievements();
  // Brief highlight on the newly unlocked badge
  requestAnimationFrame(function() {
    var badge = document.querySelector('.badge-' + key + '.unlocked');
    if (badge) {
      badge.style.animation = 'none';
      badge.offsetHeight; // force reflow
      badge.style.animation = 'badge-unlock 0.6s ease';
    }
  });
}

// ═══════════════════════════════════════════════════════
// LIVE SCORING (scorer tab — updates as positions change)
// ═══════════════════════════════════════════════════════

function initLiveScoring() {
  // Update live score whenever scorer backbone/conjugate changes
  ['scorer-bb-guide-term', 'scorer-bb-guide-int', 'scorer-bb-pass-term', 'scorer-bb-pass-int', 'scorer-conjugate'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener('change', updateLiveScore);
  });
  // Initial render
  updateLiveScore();
}

function updateLiveScore() {
  var scores = localBiophysicsScore(scorerGuide, scorerPassenger);
  var strip = document.getElementById('scorer-live-score');
  if (!strip) return;

  function setVal(id, val) {
    var el = document.getElementById(id);
    if (!el) return;
    el.textContent = val.toFixed(0);
    el.style.color = val >= 75 ? 'var(--accent-biolum)' : val >= 50 ? 'var(--void-warming)' : 'var(--void-untested)';
  }

  setVal('live-thermo', scores.Thermo);
  setVal('live-risc', scores.RISC);
  setVal('live-nucres', scores.NucRes);
  setVal('live-offtgt', scores.OffTgt);
  setVal('live-overall', scores.Overall);

  // Brief flash to show update
  strip.classList.add('score-updating');
  setTimeout(function() { strip.classList.remove('score-updating'); }, 300);
}

// ═══════════════════════════════════════════════════════
// CURIOSITY SCORE (for void cards)
// ═══════════════════════════════════════════════════════

function computeCuriosityScore(v) {
  // Curiosity = how scientifically interesting is this void?
  // Factors: novelty (hamming distance), high uncertainty, being in an underexplored region
  var novelty = Math.min(1.0, (v.hamming_distance_to_nearest || 0) / 15);
  var overallScore = (v.overall_oligovoid_score || 0) / 100;
  // Risk inversely correlates — low risk + high novelty = high curiosity
  var riskMap = { low: 1.0, medium: 0.6, high: 0.3, unknown: 0.5 };
  var riskFactor = riskMap[(v.classification || {}).exploration_risk || 'unknown'];
  var curiosity = (novelty * 0.5 + overallScore * 0.3 + riskFactor * 0.2) * 100;
  var why;
  if (novelty > 0.7) why = 'Very far from any known drug — uncharted territory';
  else if (overallScore > 0.7) why = 'High predicted score in an unexplored region';
  else if (riskFactor > 0.8) why = 'Low risk with moderate novelty — safe bet for first test';
  else why = 'Moderate novelty and feasibility';
  return { score: Math.min(100, Math.max(0, curiosity)), why: why };
}

function renderCuriosityMeter(v) {
  var c = computeCuriosityScore(v);
  return '<div class="curiosity-meter">' +
    '<span class="curiosity-icon">?</span>' +
    '<div class="curiosity-bar-track"><div class="curiosity-bar-fill" data-width="' + c.score + '%" style="width:0%"></div></div>' +
    '<span class="curiosity-label">' + c.score.toFixed(0) + '/100</span>' +
  '</div>' +
  '<div class="curiosity-why">' + c.why + '</div>';
}

// ═══════════════════════════════════════════════════════
// ONTOLOGY
// ═══════════════════════════════════════════════════════

async function loadOntology() {
  try {
    var cached = cacheGet('ontology');
    ontologyData = cached || await apiFetch('/api/ontology');
    if (!cached) cacheSet('ontology', ontologyData);
  } catch (e) { /* ignore */ }
}

// ═══════════════════════════════════════════════════════
// TAB 1: THE MAP (heatmap + territory cards)
// ═══════════════════════════════════════════════════════

async function loadModificationMap() {
  if (heatmapData) return;
  try {
    var cached = cacheGet('modmap');
    heatmapData = cached || await apiFetch('/api/modification-map');
    if (!cached) cacheSet('modmap', heatmapData);

    if (!knownPatterns) {
      var kpCached = cacheGet('known_patterns');
      var kpData = kpCached || await apiFetch('/api/known-patterns');
      if (!kpCached) cacheSet('known_patterns', kpData);
      knownPatterns = kpData.patterns || [];
    }

    renderHeatmap('guide', heatmapData.guide_strand, 'heatmap-guide', 'heatmap-y-axis-guide');
    renderHeatmap('passenger', heatmapData.passenger_strand, 'heatmap-passenger', 'heatmap-y-axis-passenger');
    renderVoidCallout();
    renderTerritoryCards();
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
  return '#000000';
}

function getRegionClass(pos1indexed, strand) {
  if (strand !== 'guide') return '';
  if (SEED_RANGE.includes(pos1indexed)) return 'seed-region';
  if (CLEAVAGE_RANGE.includes(pos1indexed)) return 'cleavage-site';
  if (OVERHANG_RANGE.includes(pos1indexed)) return 'overhang';
  return '';
}

function buildVoidSet() {
  var voids = new Set();
  if (heatmapData && heatmapData.void_positions) {
    heatmapData.void_positions.forEach(function(v) {
      voids.add(v.strand + ':' + v.position + ':' + v.modification);
    });
  }
  return voids;
}

function renderHeatmap(strand, strandData, gridId, yAxisId) {
  var grid = document.getElementById(gridId);
  var yAxis = document.getElementById(yAxisId);
  if (!grid || !yAxis) return;

  var voidSet = buildVoidSet();

  // Y-axis labels
  yAxis.innerHTML = '';
  var yHeader = document.createElement('div');
  yHeader.className = 'heatmap-y-label';
  yHeader.style.height = '22px';
  yHeader.textContent = '';
  yAxis.appendChild(yHeader);

  SUGAR_MODS.forEach(function(mod) {
    var label = document.createElement('div');
    label.className = 'heatmap-y-label';
    label.textContent = mod;
    label.style.color = MOD_COLORS[mod] || '#888';
    yAxis.appendChild(label);
  });

  // Grid
  grid.innerHTML = '';

  var headerRow = document.createElement('div');
  headerRow.className = 'heatmap-row-header';
  for (var pos = 1; pos <= 21; pos++) {
    var label = document.createElement('div');
    label.className = 'heatmap-col-label';
    label.textContent = pos;
    headerRow.appendChild(label);
  }
  grid.appendChild(headerRow);

  SUGAR_MODS.forEach(function(mod, modIdx) {
    var row = document.createElement('div');
    row.className = 'heatmap-row';

    for (var pos = 1; pos <= 21; pos++) {
      var posKey = 'position_' + pos;
      var count = (strandData[posKey] && strandData[posKey][mod]) || 0;
      var isVoid = voidSet.has(strand + ':' + pos + ':' + mod);

      var cell = document.createElement('div');
      cell.className = 'heatmap-cell';
      cell.style.background = getHeatmapColor(count);
      cell.style.color = getHeatmapTextColor(count);
      cell.textContent = count > 0 ? count : '';

      if (isVoid || count === 0) {
        cell.classList.add('void-cell');
      }

      var regionCls = getRegionClass(pos, strand);
      if (regionCls) cell.classList.add(regionCls);

      // Staggered animation
      var delay = (modIdx * 21 + pos) * 8;
      cell.style.opacity = '0';
      cell.style.transform = 'scale(0.8)';
      (function(c, d) {
        setTimeout(function() {
          c.style.transition = 'opacity 0.3s, transform 0.3s';
          c.style.opacity = '1';
          c.style.transform = 'scale(1)';
        }, d);
      })(cell, delay);

      cell.dataset.strand = strand;
      cell.dataset.pos = pos;
      cell.dataset.mod = mod;
      cell.dataset.count = count;

      cell.addEventListener('mouseenter', showHeatmapTooltip);
      cell.addEventListener('mouseleave', hideHeatmapTooltip);
      cell.addEventListener('click', handleHeatmapClick);

      row.appendChild(cell);
    }

    grid.appendChild(row);
  });
}

// Modification full names and explanations for tooltips
var MOD_FULL_NAMES = {
  "2'-OMe": "2'-O-Methyl",
  "2'-F": "2'-Fluoro",
  "LNA": "Locked Nucleic Acid",
  "cEt": "Constrained Ethyl",
  "DNA": "2'-Deoxyribonucleic Acid",
  "RNA": "Unmodified RNA",
  "UNA": "Unlocked Nucleic Acid",
  "MOE": "2'-O-Methoxyethyl"
};

var MOD_BRIEF = {
  "2'-OMe": "A methyl group on the sugar ring. The most commonly used modification \u2014 provides good nuclease protection and is well-tolerated by the cell's gene-silencing machinery (Ago2). Used in 6/8 FDA-approved siRNA drugs.",
  "2'-F": "A fluorine atom replaces the hydroxyl on the sugar. Almost the same size as natural RNA, so Ago2 accepts it easily. Best modification for the seed region where precise geometry is critical.",
  "LNA": "A methylene bridge locks the sugar rigid. Extremely stabilizing (+4\u00b0C per modification) but too stiff for the seed region and toxic in long stretches. Best used sparingly at strand ends for protection.",
  "cEt": "Similar to LNA (locked sugar) but with an ethyl bridge. Sometimes better tolerated at certain positions. Mostly used in antisense drugs, so many siRNA combinations are untested.",
  "DNA": "The natural DNA form \u2014 no 2'-OH group. Destabilizes the duplex (-1.5\u00b0C), which can help Ago2 separate the strands. Used strategically at position 1 or the cleavage site.",
  "RNA": "Unmodified, natural RNA. Survives only ~15 seconds in blood because enzymes attack the exposed 2'-OH group. Any position left as RNA is a vulnerability in the drug.",
  "UNA": "The sugar ring is broken open, making it extremely flexible (-2\u00b0C). The opposite of LNA. Used at position 1 to create thermodynamic asymmetry so Ago2 loads the correct strand.",
  "MOE": "A large methoxyethyl chain on the sugar. Excellent nuclease resistance but physically too bulky for the seed region or Ago2's narrow channel. Best at the 3' overhang for protection."
};

function getRegionInfo(strand, pos) {
  if (pos === 1) return { name: "5' End", desc: "The entry point. This position determines which strand Ago2 selects as the guide. Flexible modifications (UNA, DNA) here help ensure the correct strand loads." };
  if (pos >= 2 && pos <= 8) return { name: "Seed Region", desc: "The drug's 'address' \u2014 these positions find and bind the target mRNA. Modifications must maintain A-form helix geometry. Too rigid = reduced efficacy. Wrong shape = off-target gene silencing." };
  if (pos === 9) return { name: "Central Pivot", desc: "Transition zone between seed and cleavage. Relatively tolerant of diverse modifications. Acts as a hinge where the guide strand bends during target recognition." };
  if (pos >= 10 && pos <= 11) return { name: "Cleavage Site", desc: "Where Ago2's 'Slicer' enzyme cuts the target mRNA. Rigid/bulky modifications (LNA, cEt, MOE) BLOCK the cutting mechanism and must NEVER be placed here." };
  if (pos >= 12 && pos <= 16) return { name: "Supplementary Region", desc: "Stabilizes the guide-target pairing during cutting. More tolerant of diverse modifications. A good place to experiment with different chemistries." };
  if (pos >= 17 && pos <= 18) return { name: "3' Body", desc: "Transition to the exposed tail. Modifications here serve as an inner defense line against 3'-exonucleases that attack from the end." };
  if (pos >= 19) return { name: "3' Overhang", desc: "The most vulnerable positions \u2014 fully exposed single-stranded tail. Exonucleases attack here first. Strong protection (2'-OMe, LNA, PS backbone) is critical." };
  return { name: "", desc: "" };
}

function getModAtPositionInsight(mod, pos, strand) {
  // Contextual insight about this specific modification at this specific position
  var region = getRegionInfo(strand, pos);
  if (pos === 1 && mod === 'UNA') return 'Excellent choice: UNA at position 1 creates thermodynamic asymmetry, helping Ago2 load the guide strand preferentially. This is a well-validated strategy used in clinical programs.';
  if (pos === 1 && mod === 'DNA') return 'DNA at position 1 destabilizes the 5\' end, which can help with strand selection. A reasonable alternative to UNA for thermodynamic asymmetry.';
  if (pos >= 2 && pos <= 8 && mod === "2'-F") return 'Ideal: 2\'-F in the seed region maintains the precise A-form helix geometry needed for target recognition. Its small size mimics natural RNA perfectly.';
  if (pos >= 2 && pos <= 8 && mod === "2'-OMe") return '2\'-OMe in the seed provides good protection but is slightly bulkier than 2\'-F. Most FDA drugs alternate OMe/F in the seed for optimal balance.';
  if (pos >= 2 && pos <= 8 && mod === 'LNA') return 'Caution: LNA in the seed region can reduce efficacy due to excessive rigidity. The locked sugar prevents the flexible scanning motion needed to find the target mRNA.';
  if (pos >= 2 && pos <= 8 && mod === 'cEt') return 'Caution: Like LNA, cEt in the seed region adds rigidity that may impair target scanning. However, cEt is sometimes slightly better tolerated than LNA at certain seed positions.';
  if (pos >= 2 && pos <= 8 && mod === 'MOE') return 'Warning: MOE is physically too bulky for the seed region. Its large methoxyethyl group can distort the helix geometry needed for precise target recognition.';
  if ((pos === 10 || pos === 11) && (mod === 'LNA' || mod === 'cEt' || mod === 'MOE')) return 'CRITICAL WARNING: Rigid/bulky modifications at the cleavage site block Ago2\'s Slicer enzyme from cutting the target mRNA. This will likely destroy the drug\'s gene-silencing activity entirely.';
  if ((pos === 10 || pos === 11) && mod === 'DNA') return 'DNA at the cleavage site can help by loosening the structure slightly, making it easier for Ago2 to execute the cut. Used in some advanced designs.';
  if (pos >= 19 && (mod === "2'-OMe" || mod === 'LNA')) return 'Strong protective choice at the 3\' overhang, where exonucleases attack first. This modification shields the exposed tail from rapid degradation.';
  if (pos >= 19 && mod === 'RNA') return 'Vulnerable: Unmodified RNA at the 3\' overhang is rapidly destroyed by exonucleases. This is the most exposed position on the strand.';
  if (mod === 'RNA') return 'Unmodified RNA at this position is vulnerable to nuclease degradation. Unless this position is too sensitive for any modification, consider adding protection.';
  return '';
}

function showHeatmapTooltip(e) {
  var cell = e.currentTarget;
  var tooltip = document.getElementById('heatmap-tooltip');
  var strand = cell.dataset.strand;
  var pos = parseInt(cell.dataset.pos);
  var mod = cell.dataset.mod;
  var count = parseInt(cell.dataset.count);

  var strandLabel = strand === 'guide' ? 'Guide' : 'Passenger';
  var strandExplain = strand === 'guide'
    ? 'The guide strand is the active strand that silences the target gene.'
    : 'The passenger strand is the protective partner that gets discarded after delivery.';

  var region = getRegionInfo(strand, pos);
  var regionTag = region.name ? ' \u2014 ' + region.name : '';
  var modFull = MOD_FULL_NAMES[mod] || mod;
  var modExplain = MOD_BRIEF[mod] || '';
  var posInsight = getModAtPositionInsight(mod, pos, strand);

  var examples = '';
  if (knownPatterns && count > 0) {
    var matching = knownPatterns.filter(function(p) {
      var mods = strand === 'guide' ? p.guide_modifications : p.passenger_modifications;
      return mods && mods[pos - 1] === mod;
    }).map(function(p) { return p.drug_name; }).slice(0, 3);
    if (matching.length) examples = matching.join(', ');
  }

  tooltip.innerHTML =
    '<div class="tt-title">' + strandLabel + ' Strand, Position ' + pos + regionTag + '</div>' +
    '<div class="tt-strand-note">' + strandExplain + '</div>' +
    '<div class="tt-mod-name"><strong>' + mod + '</strong> (' + modFull + ')</div>' +
    '<div class="tt-mod-explain">' + modExplain + '</div>' +
    (region.desc ? '<div class="tt-region-explain"><strong>This region:</strong> ' + region.desc + '</div>' : '') +
    (posInsight ? '<div class="tt-insight">' + posInsight + '</div>' : '') +
    '<div class="tt-count">Published experiments using ' + mod + ' at ' + strandLabel.toLowerCase() + ' position ' + pos + ': <strong>' + count + '</strong></div>' +
    (count === 0 ? '<div class="tt-void">VOID \u2014 This specific combination has never been tested in any published siRNA experiment. It is an unexplored possibility \u2014 a gap in human knowledge.</div>' : '') +
    (examples ? '<div class="tt-examples">Used in: ' + examples + '</div>' : '');

  tooltip.style.display = 'block';
  positionTooltip(tooltip, e);
}

function hideHeatmapTooltip() {
  document.getElementById('heatmap-tooltip').style.display = 'none';
}

function positionTooltip(tooltip, e) {
  var x = e.clientX + 12;
  var y = e.clientY + 12;
  tooltip.style.left = Math.min(x, window.innerWidth - 420) + 'px';
  tooltip.style.top = Math.min(y, window.innerHeight - 300) + 'px';
}

function handleHeatmapClick(e) {
  var cell = e.currentTarget;
  var mod = cell.dataset.mod;
  var strand = cell.dataset.strand;

  var gridId = strand === 'guide' ? 'heatmap-guide' : 'heatmap-passenger';
  var grid = document.getElementById(gridId);
  var cells = grid.querySelectorAll('.heatmap-cell');

  cells.forEach(function(c) { c.classList.remove('row-highlighted'); });
  cells.forEach(function(c) {
    if (c.dataset.mod === mod && parseInt(c.dataset.count) === 0) {
      c.classList.add('row-highlighted');
    }
  });
}

function renderVoidCallout() {
  var callout = document.getElementById('void-callout');
  if (!statsData || !statsData.position_coverage) {
    callout.style.display = 'none';
    return;
  }

  var hot = statsData.position_coverage.hottest_void;
  if (!hot) {
    callout.style.display = 'none';
    return;
  }

  callout.innerHTML =
    '<strong>Most interesting void:</strong> ' + hot.position + ', ' + hot.mod + '<br>' +
    hot.why_interesting;
}

// ═══════════════════════════════════════════════════════
// TERRITORY CARDS (7 regions)
// ═══════════════════════════════════════════════════════

function renderTerritoryCards() {
  var container = document.getElementById('territory-cards');
  if (!container) return;

  // Define 7 territories with their colors and beginner-friendly descriptions
  var territories = [
    { name: "5' End", positions: '1', color: '#a855f7', borderColor: 'rgba(168,85,247,0.4)', bg: 'rgba(168,85,247,0.08)',
      desc: 'The entry point. Position 1 of the guide strand determines which strand the cell keeps for gene silencing. Flexible modifications (like UNA) here help the cell select the correct strand.' },
    { name: 'Seed', positions: '2-8', color: '#3366ff', borderColor: 'rgba(51,102,255,0.4)', bg: 'rgba(51,102,255,0.08)',
      desc: "The drug's address \u2014 these 7 positions find and bind the target gene. Must maintain precise geometry. If modifications here are too rigid, the drug can't find its target or may silence the wrong gene." },
    { name: 'Central', positions: '9', color: '#00d4ff', borderColor: 'rgba(0,212,255,0.4)', bg: 'rgba(0,212,255,0.08)',
      desc: 'Pivot point between the targeting region (seed) and the cutting region (cleavage). Tolerant of diverse modifications. Acts as a hinge in the guide strand.' },
    { name: 'Cleavage', positions: '10-11', color: '#ff4444', borderColor: 'rgba(255,68,68,0.4)', bg: 'rgba(255,68,68,0.08)',
      desc: "Where the cell's scissors (Ago2 Slicer) cut the target mRNA. Rigid modifications here BLOCK the cut entirely. Only flexible mods (2'-OMe, 2'-F, DNA) are safe." },
    { name: 'Supplementary', positions: '12-16', color: '#f59e0b', borderColor: 'rgba(245,158,11,0.4)', bg: 'rgba(245,158,11,0.08)',
      desc: 'Stabilizes the guide-target binding during cutting. The most tolerant region \u2014 a good place to experiment with diverse modifications and enhance overall drug stability.' },
    { name: "3' Body", positions: '17-18', color: '#22c55e', borderColor: 'rgba(34,197,94,0.4)', bg: 'rgba(34,197,94,0.08)',
      desc: "Inner defense line against enzymes that chew RNA from the 3' end. Protective modifications (2'-OMe) here slow degradation before it reaches the functional core." },
    { name: "3' Overhang", positions: '19-21', color: '#00d4ff', borderColor: 'rgba(0,212,255,0.4)', bg: 'rgba(0,212,255,0.08)',
      desc: "The most vulnerable positions \u2014 an exposed single-stranded tail. Enzymes attack here first. Without strong protection (LNA, 2'-OMe, PS backbone), the entire strand degrades from this end." },
  ];

  // Count voids per territory from heatmap data
  var voidSet = buildVoidSet();

  container.innerHTML = '';
  territories.forEach(function(t) {
    var posRange = parsePositionRange(t.positions);
    var voidCount = 0;
    var totalCells = posRange.length * SUGAR_MODS.length;

    posRange.forEach(function(pos) {
      SUGAR_MODS.forEach(function(mod) {
        if (voidSet.has('guide:' + pos + ':' + mod)) voidCount++;
      });
    });

    var voidPct = totalCells > 0 ? Math.round((voidCount / totalCells) * 100) : 0;

    var card = document.createElement('div');
    card.className = 'territory-card';
    card.style.background = t.bg;
    card.style.borderColor = t.borderColor;
    card.style.color = t.color;

    var posLabel = t.positions.indexOf('-') >= 0
      ? 'Guide positions ' + t.positions + ' (out of 21)'
      : 'Guide position ' + t.positions + ' (out of 21)';

    card.innerHTML =
      '<div class="territory-card-name">' + t.name + '</div>' +
      '<div class="territory-card-positions">' + posLabel + '</div>' +
      '<div class="territory-card-stat">' + voidPct + '%</div>' +
      '<div class="territory-card-label">unexplored</div>' +
      '<div class="territory-card-desc">' + t.desc + '</div>';

    container.appendChild(card);
  });
}

function parsePositionRange(str) {
  var parts = str.split('-');
  if (parts.length === 2) {
    var start = parseInt(parts[0]);
    var end = parseInt(parts[1]);
    var result = [];
    for (var i = start; i <= end; i++) result.push(i);
    return result;
  }
  return [parseInt(str)];
}

// ═══════════════════════════════════════════════════════
// INLINE PATTERN DESIGNER (Map tab)
// ═══════════════════════════════════════════════════════

function initDesigner() {
  var guideRow = document.getElementById('designer-guide');
  var passRow = document.getElementById('designer-passenger');
  if (!guideRow || !passRow) return;

  buildDesignerRow(guideRow, designerGuide, 'designer-guide');
  buildDesignerRow(passRow, designerPassenger, 'designer-passenger');

  var analyzeBtn = document.getElementById('btn-analyze-pattern');
  if (analyzeBtn) analyzeBtn.addEventListener('click', analyzeDesignerPattern);

  updateDesignerPreview();
}

function buildDesignerRow(container, mods, prefix) {
  container.innerHTML = '';
  mods.forEach(function(mod, i) {
    var sel = document.createElement('select');
    sel.className = 'designer-select';
    sel.dataset.index = i;
    sel.dataset.prefix = prefix;
    sel.style.background = modBg(mod);
    sel.style.color = MOD_COLORS[mod] || '#888';
    sel.style.borderColor = (MOD_COLORS[mod] || '#888') + '40';

    SUGAR_MODS.forEach(function(m) {
      var opt = document.createElement('option');
      opt.value = m;
      opt.textContent = SUGAR_ABBREV[m];
      if (m === mod) opt.selected = true;
      sel.appendChild(opt);
    });

    sel.addEventListener('change', function(e) {
      var idx = parseInt(e.target.dataset.index);
      var newMod = e.target.value;
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
  var c = MOD_COLORS[mod] || '#888';
  return c + '18';
}

function updateDesignerPreview() {
  var preview = document.getElementById('score-preview');
  if (!preview) return;

  var scores = localBiophysicsScore(designerGuide, designerPassenger);
  preview.innerHTML = Object.entries(scores).map(function(entry) {
    var label = entry[0];
    var val = entry[1];
    var cls = val >= 75 ? 'score-high' : val >= 50 ? 'score-mid' : 'score-low';
    return '<div class="score-mini">' +
      '<span class="score-mini-value ' + cls + '">' + val.toFixed(0) + '</span>' +
      '<span class="score-mini-label">' + label + '</span>' +
      '</div>';
  }).join('');
}

async function analyzeDesignerPattern() {
  var btn = document.getElementById('btn-analyze-pattern');
  btn.disabled = true;
  btn.textContent = 'Analyzing...';

  var conjugate = document.getElementById('designer-conjugate').value;
  try {
    var result = await apiFetch('/api/score/custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        guide_modifications: designerGuide,
        passenger_modifications: designerPassenger,
        backbone_guide: ESC_BACKBONE_GUIDE,
        backbone_passenger: ESC_BACKBONE_PASS,
        conjugate: conjugate,
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

var DELTA_TM = { "2'-OMe": 1.0, "2'-F": 1.8, LNA: 4.0, cEt: 3.5, DNA: -1.5, RNA: 0.0, UNA: -2.0, MOE: 2.0 };

function localBiophysicsScore(guide, passenger) {
  var allMods = guide.concat(passenger);
  var nPos = allMods.length;
  var totalDeltaTm = allMods.reduce(function(sum, m) { return sum + (DELTA_TM[m] || 0); }, 0);
  var avgPerPos = nPos > 0 ? totalDeltaTm / nPos : 0;
  var effectiveDelta = avgPerPos * Math.sqrt(nPos);
  var thermoScore;
  if (effectiveDelta >= 5 && effectiveDelta <= 15) thermoScore = 100 - Math.abs(effectiveDelta - 10) * 2;
  else if (effectiveDelta < 5) thermoScore = Math.max(0, 60 + effectiveDelta * 8);
  else thermoScore = Math.max(0, 100 - (effectiveDelta - 15) * 4);
  thermoScore = Math.min(100, Math.max(0, thermoScore));

  var riscScore = 100;
  var seedMods = guide.slice(1, 8);
  seedMods.forEach(function(m) {
    if (m === 'LNA') riscScore -= 15;
    if (m === 'cEt') riscScore -= 12;
    if (m === 'MOE') riscScore -= 10;
  });
  var cleavMods = guide.slice(9, 11);
  cleavMods.forEach(function(m) {
    if (['LNA', 'cEt', 'MOE'].includes(m)) riscScore -= 25;
  });
  if (guide[0] === 'UNA') riscScore += 8;
  var rigidCount = guide.filter(function(m) { return ['LNA', 'cEt', 'MOE'].includes(m); }).length;
  if (rigidCount / 21 > 0.3) riscScore -= 15;
  riscScore = Math.min(100, Math.max(0, riscScore));

  var nucScore = 40;
  var omeCount = allMods.filter(function(m) { return m === "2'-OMe"; }).length;
  nucScore += Math.min(20, omeCount * 2);
  var rnaCount = allMods.filter(function(m) { return m === 'RNA'; }).length;
  nucScore -= Math.min(30, rnaCount * 5);
  var lnaCount = allMods.filter(function(m) { return ['LNA', 'cEt'].includes(m); }).length;
  nucScore += Math.min(15, lnaCount * 5);
  nucScore = Math.min(100, Math.max(0, nucScore));

  var offTarget = 30;
  var passSeedMods = passenger.slice(1, 8);
  var passOmeInSeed = passSeedMods.filter(function(m) { return m === "2'-OMe"; }).length;
  offTarget -= passOmeInSeed * 3;
  offTarget = Math.min(100, Math.max(0, offTarget));
  var offTargetScore = 100 - offTarget;

  var overall = thermoScore * 0.20 + riscScore * 0.35 + nucScore * 0.25 + offTargetScore * 0.20;

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
  var minScore = document.getElementById('filter-min-score');
  var minScoreVal = document.getElementById('filter-min-score-value');
  if (minScore) {
    var filterDebounce = null;
    minScore.addEventListener('input', function() {
      minScoreVal.textContent = minScore.value;
      clearTimeout(filterDebounce);
      filterDebounce = setTimeout(loadVoids, 400);
    });
    minScore.addEventListener('change', loadVoids);
  }

  var voidTypeEl = document.getElementById('filter-void-type');
  if (voidTypeEl) voidTypeEl.addEventListener('change', loadVoids);
  var sortEl = document.getElementById('filter-sort');
  if (sortEl) sortEl.addEventListener('change', loadVoids);
}

async function loadVoids() {
  var container = document.getElementById('void-cards');
  if (!container) return;

  var minScore = document.getElementById('filter-min-score');
  var voidType = document.getElementById('filter-void-type');
  var sortBy = document.getElementById('filter-sort');
  var minScoreVal = minScore ? minScore.value : 0;
  var voidTypeVal = voidType ? voidType.value : '';
  var sortByVal = sortBy ? sortBy.value : 'overall_oligovoid_score';

  container.innerHTML = '<div class="no-data"><div class="spinner"></div> Loading voids...</div>';

  try {
    var url = '/api/voids?limit=50&min_score=' + minScoreVal + '&sort_by=' + sortByVal;
    if (voidTypeVal) url += '&void_type=' + voidTypeVal;

    var data = await apiFetch(url);
    var voids = data.voids || [];

    if (!voids.length) {
      container.innerHTML = '<div class="no-data">No voids match these filters.</div>';
      return;
    }

    container.innerHTML = '';
    voids.forEach(function(v, idx) {
      container.appendChild(createVoidCard(v, idx + 1));
    });

    requestAnimationFrame(function() {
      container.querySelectorAll('.score-bar-fill, .curiosity-bar-fill').forEach(function(bar) {
        bar.style.width = bar.dataset.width;
      });
    });
  } catch (err) {
    container.innerHTML = '<div class="no-data" style="color:var(--void-untested);">Error: ' + err.message + '</div>';
  }
}

// Expand void ID abbreviations for beginners
// e.g. "G2_UNA" -> "Guide Position 2, UNA (Unlocked Nucleic Acid)"
function expandVoidId(voidId) {
  if (!voidId) return '';
  var parts = voidId.split('_');
  var expanded = [];
  parts.forEach(function(part) {
    // Check for position codes like G2, G14, P5
    var posMatch = part.match(/^([GP])(\d+)$/);
    if (posMatch) {
      var strandName = posMatch[1] === 'G' ? 'Guide' : 'Passenger';
      expanded.push(strandName + ' pos ' + posMatch[2]);
      return;
    }
    // Check for modification names
    if (MOD_FULL_NAMES[part]) {
      expanded.push(part + ' (' + MOD_FULL_NAMES[part] + ')');
      return;
    }
    // Check abbreviations
    var modFromAbbrev = ABBREV_TO_MOD[part] || ABBREV_TO_MOD[part.toLowerCase()];
    if (modFromAbbrev) {
      expanded.push(modFromAbbrev + ' (' + MOD_FULL_NAMES[modFromAbbrev] + ')');
      return;
    }
    expanded.push(part);
  });
  return expanded.join(', ');
}

function createVoidCard(v, rank) {
  var card = document.createElement('div');
  card.className = 'void-card';

  var overallScore = v.overall_oligovoid_score || 0;
  var scoreColor = scoreColorFn(overallScore);

  var classification = v.classification || {};
  var voidType = classification.void_type || 'unknown';
  var risk = classification.exploration_risk || 'unknown';
  var complexity = classification.estimated_synthesis_complexity || '';

  var expandedId = expandVoidId(v.void_id);

  var scores = [
    { label: 'RISC Loading', title: 'How easily the guide strand loads into the Ago2 protein for gene silencing', value: v.risc_loading_score },
    { label: 'Thermo Stability', title: 'Whether the two strands stay paired during delivery (ideal melting temp: 50-65\u00b0C)', value: v.thermodynamic_score },
    { label: 'Nuclease Resistance', title: 'How well the drug resists destruction by blood enzymes', value: v.nuclease_resistance_score },
    { label: 'Off-target Safety', title: 'Risk of accidentally silencing the wrong gene (higher = safer)', value: v.off_target_risk_score ? (100 - v.off_target_risk_score) : null },
  ];

  // Build chemistry fingerprint from guide notation
  var fingerprint = '';
  if (v.guide_notation) {
    fingerprint = '<div class="chem-fingerprint"><span class="chem-fingerprint-label">Chemistry:</span>';
    v.guide_notation.split('').forEach(function(ch) {
      var mod = ABBREV_TO_MOD[ch];
      if (mod) {
        fingerprint += '<div class="chem-fp-block" style="background:' + MOD_COLORS[mod] + '" title="' + mod + '">' + ch + '</div>';
      }
    });
    fingerprint += '</div>';
  }

  card.innerHTML =
    '<div class="void-card-header">' +
      '<div>' +
        '<span class="void-rank">#' + rank + '</span>' +
        '<span class="void-id" title="' + expandedId + '">' + v.void_id + '</span>' +
        (expandedId !== v.void_id ? '<div class="void-id-expanded">' + expandedId + '</div>' : '') +
      '</div>' +
      '<div style="text-align:right;">' +
        '<div class="void-overall-score" style="color:' + scoreColor + '">' + overallScore.toFixed(0) + '</div>' +
        '<div class="void-overall-label">Score</div>' +
      '</div>' +
    '</div>' +
    '<div class="void-notation">' +
      '<span class="strand-label-inline">Guide:</span>' +
      "<span class=\"notation-chars\">5'-" + colorizeNotation(v.guide_notation || '') + "-3'</span>" +
    '</div>' +
    '<div class="void-notation">' +
      '<span class="strand-label-inline">Pass:</span>' +
      "<span class=\"notation-chars\">3'-" + colorizeNotation(v.passenger_notation || '') + "-5'" +
      (v.conjugate ? ' <span style="color:var(--accent-purple);font-size:0.62rem;">[' + v.conjugate + ']</span>' : '') + '</span>' +
    '</div>' +
    fingerprint +
    (v.description ? '<div class="void-description">' + v.description + '</div>' : '') +
    (v.one_line_insight ? '<div class="void-insight">"' + v.one_line_insight + '"</div>' : '') +
    '<div class="score-bars">' +
      scores.map(function(s) {
        if (s.value == null) return '';
        var c = scoreColorFn(s.value);
        var cls = s.value >= 75 ? 'bg-score-high' : s.value >= 50 ? 'bg-score-mid' : 'bg-score-low';
        return '<div class="score-bar-item" title="' + (s.title || '') + '">' +
          '<div class="score-bar-top">' +
            '<span class="score-bar-label">' + s.label + '</span>' +
            '<span class="score-bar-value" style="color:' + c + '">' + s.value.toFixed(0) + '</span>' +
          '</div>' +
          '<div class="score-bar-track">' +
            '<div class="score-bar-fill ' + cls + '" data-width="' + s.value + '%" style="width:0%"></div>' +
          '</div>' +
        '</div>';
      }).join('') +
    '</div>' +
    '<div class="void-overall-bar">' +
      '<div class="score-bar-top">' +
        '<span class="score-bar-label">Overall OligoVoid Score</span>' +
        '<span class="score-bar-value" style="color:' + scoreColor + '">' + overallScore.toFixed(0) + '/100</span>' +
      '</div>' +
      '<div class="score-bar-track">' +
        '<div class="score-bar-fill" data-width="' + overallScore + '%" style="width:0%;background:' + scoreColor + '"></div>' +
      '</div>' +
    '</div>' +
    (v.closest_known_pattern_id ?
      '<div class="void-nearest">Nearest drug: <strong style="color:var(--accent-cyan)">' + v.closest_known_pattern_id + '</strong> (' + (v.hamming_distance_to_nearest || '?') + ' positions differ)</div>' : '') +
    '<div class="void-badges">' +
      '<span class="void-badge ' + (risk === 'low' ? 'feasibility-high' : risk === 'medium' ? 'feasibility-medium' : 'feasibility-low') + '">' + (risk === 'low' ? 'High' : risk === 'medium' ? 'Medium' : 'Low') + ' Feasibility</span>' +
      '<span class="void-badge type-badge">' + formatVoidType(voidType) + '</span>' +
      (complexity ? '<span class="void-badge" style="border-color:var(--border-bright);color:var(--text-secondary);">' + complexity + '</span>' : '') +
    '</div>' +
    renderCuriosityMeter(v) +
    (v.recommended_experiment ?
      '<div class="void-experiment"><strong>First experiment:</strong><br>"' + v.recommended_experiment + '"</div>' : '') +
    '<button class="void-expand-btn" onclick="toggleVoidExpand(this)">&#9660; More</button>' +
    '<div class="void-expanded">' +
      (v.why_untested ? '<p style="margin-bottom:0.4rem;"><strong style="color:var(--accent-cyan);font-size:0.65rem;text-transform:uppercase;">Why never tested:</strong><br><span style="color:var(--text-secondary);font-size:0.72rem;">' + v.why_untested + '</span></p>' : '') +
      (v.confidence_level ? '<p style="margin-bottom:0.4rem;"><strong style="color:var(--accent-cyan);font-size:0.65rem;text-transform:uppercase;">Confidence:</strong> <span class="mono" style="color:' + (v.confidence_level === 'high' ? 'var(--accent-biolum)' : 'var(--void-warming)') + '">' + v.confidence_level + '</span></p>' : '') +
      (v.predicted_knockdown_pct ? '<p><strong style="color:var(--accent-cyan);font-size:0.65rem;text-transform:uppercase;">Predicted Knockdown:</strong> <span class="mono color-green">' + v.predicted_knockdown_pct + '%</span></p>' : '') +
    '</div>';

  return card;
}

function toggleVoidExpand(btn) {
  var expanded = btn.nextElementSibling;
  expanded.classList.toggle('show');
  btn.innerHTML = expanded.classList.contains('show') ? '&#9650; Less' : '&#9660; More';
}

function colorizeNotation(notation) {
  return notation.split('').map(function(ch) {
    var mod = ABBREV_TO_MOD[ch];
    if (mod) {
      return '<span style="color:' + MOD_COLORS[mod] + '">' + ch + '</span>';
    }
    return ch;
  }).join('');
}

function formatVoidType(type) {
  return (type || '').replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
}

function scoreColorFn(val) {
  if (val >= 75) return '#00ff88';
  if (val >= 50) return '#ff8800';
  return '#ff3366';
}

// ═══════════════════════════════════════════════════════
// TAB 3: FDA REALITY CHECK
// ═══════════════════════════════════════════════════════

async function loadFDAValidation() {
  if (fdaLoaded) return;
  var loading = document.getElementById('fda-loading');
  if (loading) loading.style.display = 'flex';

  try {
    var data = await apiFetch('/api/validation/fda');
    renderFDACards(data.predictions || []);
    renderFDASummary(data.summary || {});
    fdaLoaded = true;
    unlockAchievement('fda');
  } catch (err) {
    showToast('Failed to load FDA validation: ' + err.message, true);
  } finally {
    if (loading) loading.style.display = 'none';
  }
}

function renderFDACards(predictions) {
  var container = document.getElementById('fda-drug-cards');
  if (!container) return;

  container.innerHTML = predictions.map(function(p) {
    var lightClass = 'traffic-' + p.traffic_light;
    var icon = p.direction_correct ? '&#x2713;' : '&#x26a0;&#xfe0f;';
    var clinical = p.clinical_efficacy_pct || 0;
    var predicted = p.biophysics_score || 0;

    return '<div class="fda-drug-card ' + lightClass + '">' +
      '<div class="fda-drug-header">' +
        '<div>' +
          '<div class="fda-drug-name">' + p.drug + ' (' + p.brand + ')</div>' +
          '<div class="fda-drug-meta">Treats: ' + p.target + ' | Approved: ' + p.year_approved + ' | ' + p.conjugate + '</div>' +
        '</div>' +
      '</div>' +
      '<div class="fda-bar-row">' +
        '<span class="fda-bar-label">Clinical result:</span>' +
        '<div class="fda-bar-track"><div class="fda-bar-fill clinical" style="width:' + clinical + '%"></div></div>' +
        '<span class="fda-bar-value">' + clinical + '%</span>' +
      '</div>' +
      '<div class="fda-bar-row">' +
        '<span class="fda-bar-label">OligoVoid score:</span>' +
        '<div class="fda-bar-track"><div class="fda-bar-fill predicted" style="width:' + predicted + '%"></div></div>' +
        '<span class="fda-bar-value">' + predicted + '%</span>' +
      '</div>' +
      '<div class="fda-drug-verdict">' +
        '<span class="verdict-icon">' + icon + '</span>' +
        (p.direction_correct ? 'Correctly identified as high-efficacy drug' : 'Classification did not match') +
        (p.error_pct != null ? ' | Error: ' + p.error_pct + '%' : '') +
        '<br><br>' + (p.plain_english || '') +
      '</div>' +
    '</div>';
  }).join('');
}

function renderFDASummary(summary) {
  var statsEl = document.getElementById('fda-summary-stats');
  var interpEl = document.getElementById('fda-summary-interpretation');
  if (!statsEl || !interpEl) return;

  statsEl.innerHTML =
    '<div class="fda-stat">' +
      '<span class="fda-stat-value">' + (summary.drugs_correctly_classified_high || '?') + '/5</span>' +
      '<span class="fda-stat-label">Correctly Identified</span>' +
    '</div>' +
    '<div class="fda-stat">' +
      '<span class="fda-stat-value">' + (summary.ranking_spearman || '?') + '</span>' +
      '<span class="fda-stat-label">Spearman &rho;</span>' +
    '</div>' +
    '<div class="fda-stat">' +
      '<span class="fda-stat-value">' + (summary.mean_absolute_error || '?') + '%</span>' +
      '<span class="fda-stat-label">Mean Absolute Error</span>' +
    '</div>';

  interpEl.innerHTML =
    '<p><strong>What this means:</strong> A random model would correctly identify ~2-3 of 5 drugs by chance. ' +
    'OligoVoid identifies ' + (summary.drugs_correctly_classified_high || '?') + '/5, ' +
    'suggesting the scoring system captures real chemical signals from the training data.</p>' +
    '<p style="margin-top:0.5rem;font-style:italic;font-size:0.85rem">' + (summary.honest_interpretation || '') + '</p>';
}

// ═══════════════════════════════════════════════════════
// TAB 4: DMTL
// ═══════════════════════════════════════════════════════

function initDMTLControls() {
  var slider = document.getElementById('dmtl-cycles');
  var label = document.getElementById('dmtl-cycles-value');
  if (slider) {
    slider.addEventListener('input', function() {
      label.textContent = slider.value;
    });
  }

  var btn = document.getElementById('btn-run-dmtl');
  if (btn) btn.addEventListener('click', runDMTLSimulation);
}

async function loadDMTL() {
  try {
    var data = await apiFetch('/api/dmtl/latest');
    if (data && data.cycles && data.cycles.length) {
      renderDMTLResults(data);
    }
  } catch (e) { /* ignore */ }
}

async function runDMTLSimulation() {
  var btn = document.getElementById('btn-run-dmtl');
  var loading = document.getElementById('dmtl-loading');
  var counter = document.getElementById('dmtl-cycle-counter');
  var acqFn = document.getElementById('dmtl-acq-fn').value;
  var nCycles = parseInt(document.getElementById('dmtl-cycles').value);

  btn.disabled = true;
  loading.style.display = 'flex';
  counter.textContent = '0';

  var currentCount = 0;
  var counterInterval = setInterval(function() {
    if (currentCount < nCycles) {
      currentCount++;
      counter.textContent = currentCount;
    }
  }, 800);

  try {
    var data = await apiFetch('/api/dmtl/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ acquisition_function: acqFn, n_cycles: nCycles }),
    });

    clearInterval(counterInterval);
    counter.textContent = nCycles;
    loading.style.display = 'none';

    renderDMTLResults(data);
    unlockAchievement('dmtl');

    // Show strategy comparison if available
    if (data.strategy_comparison) {
      renderStrategyComparison(data.strategy_comparison, acqFn);
    }
  } catch (err) {
    clearInterval(counterInterval);
    loading.style.display = 'none';
    showToast('DMTL simulation failed: ' + err.message, true);
  } finally {
    btn.disabled = false;
  }
}

function renderDMTLResults(data) {
  var timeline = document.getElementById('dmtl-timeline');
  var summary = document.getElementById('dmtl-summary');
  var cycles = data.cycles || [];

  timeline.innerHTML = '';
  cycles.forEach(function(c, idx) {
    var card = document.createElement('div');
    card.className = 'dmtl-cycle-card';

    var infoGain = c.info_gain || 0;
    var uncBefore = c.uncertainty_before || 0;
    var uncAfter = c.uncertainty_after || 0;

    card.innerHTML =
      '<div class="dmtl-cycle-num">' + c.cycle + '</div>' +
      '<div class="dmtl-cycle-body">' +
        '<div class="dmtl-cycle-void">Recommend ' + c.void_tested + '</div>' +
        '<div class="dmtl-cycle-reason">' + truncate(c.reason || 'Active learning selection', 120) + '</div>' +
        '<div class="dmtl-cycle-stats">' +
          '<span class="dmtl-cycle-stat">Uncertainty: <span class="val">' + uncBefore.toFixed(3) + ' &rarr; ' + uncAfter.toFixed(3) + '</span></span>' +
          '<span class="dmtl-cycle-stat">Info gain: <span class="val">' + infoGain.toFixed(4) + '</span></span>' +
        '</div>' +
      '</div>';

    timeline.appendChild(card);
    setTimeout(function() { card.classList.add('visible'); }, idx * 500);
  });

  drawCoverageCurve(cycles);

  if (data.summary) {
    var s = data.summary;
    var reduction = s.uncertainty_reduction_pct;
    summary.innerHTML =
      '<strong>' + (data.title || 'DMTL Results') + '</strong><br>' +
      s.total_cycles + ' cycles completed.' +
      (reduction != null ? ' Uncertainty reduced by <strong>' + reduction.toFixed(1) + '%</strong>.' : '') +
      (cycles.length > 0 ? '<br>First cycle info gain: <strong>' + (cycles[0].info_gain || 0).toFixed(4) + '</strong>. Last cycle: <strong>' + (cycles[cycles.length - 1].info_gain || 0).toFixed(4) + '</strong> (diminishing returns = model converging).' : '');
  }
}

function renderStrategyComparison(comparison, activeStrategy) {
  var container = document.getElementById('dmtl-strategy-compare');
  var cardsEl = document.getElementById('strategy-cards');
  if (!container || !cardsEl) return;

  container.style.display = 'block';

  var strategies = comparison || [];
  cardsEl.innerHTML = strategies.map(function(s) {
    var isActive = s.name && s.name.toLowerCase().includes(activeStrategy);
    return '<div class="strategy-card' + (isActive ? ' active' : '') + '">' +
      '<div class="strategy-card-name">' + (s.name || 'Unknown') + '</div>' +
      '<div class="strategy-card-val">' + (s.coverage_pct || 0).toFixed(1) + '%</div>' +
      '<div class="strategy-card-desc">coverage after ' + (s.cycles || 0) + ' cycles</div>' +
    '</div>';
  }).join('');
}

function drawCoverageCurve(cycles) {
  var canvas = document.getElementById('coverage-canvas');
  if (!canvas) return;

  var ctx = canvas.getContext('2d');
  var dpr = window.devicePixelRatio || 1;
  var rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = 280 * dpr;
  canvas.style.width = rect.width + 'px';
  canvas.style.height = '280px';
  ctx.scale(dpr, dpr);

  var W = rect.width;
  var H = 280;
  var padLeft = 60;
  var padRight = 20;
  var padTop = 20;
  var padBottom = 40;
  var plotW = W - padLeft - padRight;
  var plotH = H - padTop - padBottom;

  ctx.clearRect(0, 0, W, H);

  if (!cycles.length) return;

  var points = cycles.map(function(c) { return c.uncertainty_before || 0; });
  points.push(cycles[cycles.length - 1].uncertainty_after || 0);

  var maxUncertainty = Math.max.apply(null, points.concat([0.6]));

  // Grid
  ctx.strokeStyle = '#1e2840';
  ctx.lineWidth = 1;
  for (var i = 0; i <= 5; i++) {
    var y = padTop + (plotH / 5) * i;
    ctx.beginPath();
    ctx.moveTo(padLeft, y);
    ctx.lineTo(padLeft + plotW, y);
    ctx.stroke();
  }

  // Y axis labels
  ctx.fillStyle = '#8892b0';
  ctx.font = '11px "Space Mono", monospace';
  ctx.textAlign = 'right';
  for (var i = 0; i <= 5; i++) {
    var val = maxUncertainty * (1 - i / 5);
    var y = padTop + (plotH / 5) * i;
    ctx.fillText(val.toFixed(2), padLeft - 8, y + 4);
  }

  // X axis labels
  ctx.textAlign = 'center';
  for (var i = 0; i < points.length; i++) {
    var x = padLeft + (plotW / (points.length - 1)) * i;
    ctx.fillText(i === 0 ? 'Start' : 'C' + i, x, H - padBottom + 18);
  }

  // Line
  ctx.strokeStyle = '#00ff88';
  ctx.lineWidth = 2;
  ctx.lineJoin = 'round';
  ctx.beginPath();
  points.forEach(function(val, i) {
    var x = padLeft + (plotW / (points.length - 1)) * i;
    var y = padTop + plotH * (1 - val / maxUncertainty);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Glow
  ctx.strokeStyle = 'rgba(0, 255, 136, 0.2)';
  ctx.lineWidth = 6;
  ctx.beginPath();
  points.forEach(function(val, i) {
    var x = padLeft + (plotW / (points.length - 1)) * i;
    var y = padTop + plotH * (1 - val / maxUncertainty);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Dots
  ctx.fillStyle = '#00ff88';
  points.forEach(function(val, i) {
    var x = padLeft + (plotW / (points.length - 1)) * i;
    var y = padTop + plotH * (1 - val / maxUncertainty);
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
// TAB 5: VELOCITY
// ═══════════════════════════════════════════════════════

async function loadVelocity() {
  try {
    var cached = cacheGet('velocity');
    var data = cached || await apiFetch('/api/velocity/top');
    if (!cached) cacheSet('velocity', data);

    var voids = data.voids || [];

    var hot = voids.filter(function(v) { return v.classification === 'hot'; });
    var warming = voids.filter(function(v) { return v.classification === 'warming'; });
    var cold = voids.filter(function(v) { return v.classification === 'cold'; });

    renderVelocityColumn('velocity-hot', hot, '#ff3366');
    renderVelocityColumn('velocity-warming', warming, '#ff8800');
    renderVelocityColumn('velocity-cold', cold, '#3366ff');
  } catch (err) {
    showToast('Failed to load velocity data', true);
  }
}

function renderVelocityColumn(containerId, voids, accentColor) {
  var container = document.getElementById(containerId);
  if (!container) return;

  if (!voids.length) {
    container.innerHTML = '<div class="no-data">No voids in this category.</div>';
    return;
  }

  container.innerHTML = '';
  voids.forEach(function(v) {
    var card = document.createElement('div');
    card.className = 'velocity-card';

    var papers = [
      v.papers_2018_2020 || 0,
      v.papers_2020_2022 || 0,
      v.papers_2022_2024 || 0,
      v.papers_2024_2026 || 0,
    ];
    var maxPapers = Math.max.apply(null, papers.concat([1]));

    var trend = v.velocity_trend || 0;
    var trendArrow = trend > 0.3 ? '&#9650;' : trend < -0.3 ? '&#9660;' : '&#9654;';

    card.innerHTML =
      '<div class="velocity-card-header">' +
        '<span class="velocity-card-id">' + v.void_id + '</span>' +
        '<span class="velocity-card-score" style="color:' + scoreColorFn(v.overall_score || 0) + '">' + (v.overall_score || 0).toFixed(0) + '</span>' +
      '</div>' +
      '<div class="velocity-card-desc">' + truncate(v.description || '', 80) + '</div>' +
      '<div class="velocity-sparkline">' +
        papers.map(function(p) {
          var h = Math.max(2, (p / maxPapers) * 30);
          return '<div class="sparkline-bar" style="height:' + h + 'px;background:' + accentColor + '"></div>';
        }).join('') +
      '</div>' +
      '<div class="sparkline-labels">' +
        "<span>'18-20</span><span>'20-22</span><span>'22-24</span><span>'24-26</span>" +
      '</div>' +
      '<div class="velocity-trend" style="color:' + accentColor + '">' +
        trendArrow + ' Trend: ' + (trend > 0 ? '+' : '') + trend.toFixed(1) + ' papers/window' +
      '</div>' +
      (v.classification === 'hot' ? '<div class="velocity-urgency">Urgency: MOVE THIS WEEK</div>' : '');

    container.appendChild(card);
  });
}

// ═══════════════════════════════════════════════════════
// TAB 6: CUSTOM SCORER (21-position builder)
// ═══════════════════════════════════════════════════════

function initScorer() {
  var btn = document.getElementById('btn-score-pattern');
  if (btn) btn.addEventListener('click', scoreCustomPattern);
}

function initScorerPositions() {
  buildScorerPositions('scorer-guide-positions', scorerGuide, 'guide');
  buildScorerPositions('scorer-passenger-positions', scorerPassenger, 'passenger');
  buildScorerRegionLabels();
}

function buildScorerPositions(containerId, mods, strand) {
  var container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';

  mods.forEach(function(mod, i) {
    var pos = document.createElement('div');
    pos.className = 'scorer-pos';
    pos.style.background = modBg(mod);
    pos.style.borderColor = (MOD_COLORS[mod] || '#888') + '40';

    pos.innerHTML =
      '<span class="scorer-pos-num">' + (i + 1) + '</span>' +
      '<span class="scorer-pos-mod" style="color:' + (MOD_COLORS[mod] || '#888') + '">' + (SUGAR_ABBREV[mod] || '?') + '</span>';

    (function(index, strandName, cId) {
      pos.addEventListener('click', function() {
        openModPicker(
          (strandName === 'guide' ? 'Guide' : 'Passenger') + ' Position ' + (index + 1),
          strandName === 'guide' ? scorerGuide[index] : scorerPassenger[index],
          function(newMod) {
            if (strandName === 'guide') scorerGuide[index] = newMod;
            else scorerPassenger[index] = newMod;
            buildScorerPositions(cId, strandName === 'guide' ? scorerGuide : scorerPassenger, strandName);
            updateLiveScore();
          }
        );
      });
    })(i, strand, containerId);

    container.appendChild(pos);
  });
}

function buildScorerRegionLabels() {
  var container = document.getElementById('scorer-guide-regions');
  if (!container) return;
  container.innerHTML = '';

  for (var i = 1; i <= 21; i++) {
    var marker = document.createElement('div');
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
      marker.textContent = i === 19 ? "3'OH" : '';
    }

    container.appendChild(marker);
  }
}

async function scoreCustomPattern() {
  var btn = document.getElementById('btn-score-pattern');
  var resultsEl = document.getElementById('scorer-results');
  var compEl = document.getElementById('scorer-comparison');

  btn.disabled = true;
  btn.textContent = 'Scoring...';
  resultsEl.style.display = 'none';
  compEl.style.display = 'none';

  var bbGuideTerm = document.getElementById('scorer-bb-guide-term').value;
  var bbGuideInt = document.getElementById('scorer-bb-guide-int').value;
  var bbPassTerm = document.getElementById('scorer-bb-pass-term').value;
  var bbPassInt = document.getElementById('scorer-bb-pass-int').value;

  var backboneGuide = [];
  var backbonePass = [];
  for (var i = 0; i < 20; i++) {
    var isTerminal = i < 2 || i >= 18;
    backboneGuide.push(isTerminal ? bbGuideTerm : bbGuideInt);
    backbonePass.push(isTerminal ? bbPassTerm : bbPassInt);
  }

  var conjugate = document.getElementById('scorer-conjugate').value;

  try {
    var result = await apiFetch('/api/score/custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        guide_modifications: scorerGuide,
        passenger_modifications: scorerPassenger,
        backbone_guide: backboneGuide,
        backbone_passenger: backbonePass,
        conjugate: conjugate,
      }),
    });

    renderScorerResults(result, resultsEl);
    resultsEl.style.display = 'block';

    renderComparison(result, compEl);
    compEl.style.display = 'block';

    unlockAchievement('scorer');

    requestAnimationFrame(function() {
      resultsEl.querySelectorAll('.score-bar-fill').forEach(function(bar) {
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
  var overall = result.overall_oligovoid_score || 0;
  var scoreColor = scoreColorFn(overall);

  var bars = [
    { label: 'Thermodynamic', value: result.thermodynamic_score },
    { label: 'RISC Loading', value: result.risc_loading_score },
    { label: 'Nuclease Resistance', value: result.nuclease_resistance_score },
    { label: 'Off-Target Risk', value: result.off_target_risk_score ? (100 - result.off_target_risk_score) : null },
  ];

  container.innerHTML =
    '<h3>Score Results</h3>' +
    '<div style="display:flex;align-items:baseline;gap:1rem;margin-bottom:1rem;">' +
      '<span class="mono" style="font-size:2.2rem;font-weight:700;color:' + scoreColor + '">' + overall.toFixed(1) + '</span>' +
      '<span style="color:var(--text-secondary);font-size:0.82rem;">/100 Overall OligoVoid Score</span>' +
    '</div>' +
    '<div class="score-bars">' +
      bars.map(function(b) {
        if (b.value == null) return '';
        var c = scoreColorFn(b.value);
        var cls = b.value >= 75 ? 'bg-score-high' : b.value >= 50 ? 'bg-score-mid' : 'bg-score-low';
        return '<div class="score-bar-item">' +
          '<div class="score-bar-top">' +
            '<span class="score-bar-label">' + b.label + '</span>' +
            '<span class="score-bar-value" style="color:' + c + '">' + b.value.toFixed(1) + '</span>' +
          '</div>' +
          '<div class="score-bar-track">' +
            '<div class="score-bar-fill ' + cls + '" data-width="' + b.value + '%" style="width:0%"></div>' +
          '</div>' +
        '</div>';
      }).join('') +
    '</div>' +
    (result.guide_display ?
      '<div style="margin-top:1rem;padding:0.8rem;background:var(--bg);border-radius:var(--radius);font-family:var(--font-mono);font-size:0.7rem;color:var(--text-mono);white-space:pre-wrap;overflow-x:auto;">Guide:     ' + result.guide_display + '\nPassenger: ' + (result.passenger_display || '') + '</div>' : '') +
    (result.classification ?
      '<div class="void-badges" style="margin-top:0.8rem;">' +
        '<span class="void-badge type-badge">' + formatVoidType(result.classification.void_type || '') + '</span>' +
        '<span class="void-badge" style="border-color:var(--border-bright);color:var(--text-secondary);">Risk: ' + (result.classification.exploration_risk || '?') + '</span>' +
        '<span class="void-badge" style="border-color:var(--border-bright);color:var(--text-secondary);">Synthesis: ' + (result.classification.estimated_synthesis_complexity || '?') + '</span>' +
      '</div>' : '');
}

function renderComparison(result, container) {
  if (!knownPatterns || !knownPatterns.length) {
    container.style.display = 'none';
    return;
  }

  var nearestId = result.closest_known_pattern_id;
  var nearest = knownPatterns.find(function(p) { return p.pattern_id === nearestId; });
  if (!nearest) nearest = knownPatterns[0];

  var hamming = result.hamming_distance_to_nearest || '?';

  container.innerHTML =
    '<h4>Compared to Nearest Known: ' + nearest.drug_name + ' (' + nearest.pattern_id + ')</h4>' +
    '<div style="font-size:0.72rem;color:var(--text-secondary);margin-bottom:0.5rem;">' +
      'Hamming distance: <span class="mono color-cyan">' + hamming + '</span> positions differ' +
    '</div>' +
    '<div style="font-size:0.72rem;margin-bottom:0.3rem;">' +
      '<span style="color:var(--text-secondary);">Known:</span> ' +
      '<span class="mono" style="color:var(--text-mono);">' + nearest.guide_notation + '</span>' +
      '<span style="color:var(--text-secondary);margin-left:0.5rem;">KD: ' + (nearest.reported_knockdown || '?') + '%</span>' +
    '</div>' +
    '<div style="font-size:0.72rem;">' +
      '<span style="color:var(--text-secondary);">Yours:</span> ' +
      '<span class="mono" style="color:var(--accent-cyan);">' + scorerGuide.map(function(m) { return SUGAR_ABBREV[m]; }).join('') + '</span>' +
    '</div>';
}

// ═══════════════════════════════════════════════════════
// MODIFICATION PICKER POPUP
// ═══════════════════════════════════════════════════════

function initModPicker() {
  var closeBtn = document.getElementById('mod-picker-close');
  if (closeBtn) closeBtn.addEventListener('click', closeModPicker);
  var overlay = document.getElementById('mod-picker-overlay');
  if (overlay) {
    overlay.addEventListener('click', function(e) {
      if (e.target.id === 'mod-picker-overlay') closeModPicker();
    });
  }
}

function openModPicker(title, currentMod, callback) {
  var overlay = document.getElementById('mod-picker-overlay');
  var titleEl = document.getElementById('mod-picker-title');
  var optionsEl = document.getElementById('mod-picker-options');

  titleEl.textContent = title;
  pickerCallback = callback;

  optionsEl.innerHTML = SUGAR_MODS.map(function(mod) {
    var selected = mod === currentMod ? 'selected' : '';
    return '<div class="mod-picker-option ' + selected + '" data-mod="' + mod + '" onclick="selectMod(this)">' +
      '<span class="mod-picker-dot" style="background:' + MOD_COLORS[mod] + '"></span>' +
      '<span class="mod-picker-name">' + SUGAR_ABBREV[mod] + ' ' + mod + '</span>' +
    '</div>';
  }).join('');

  overlay.style.display = 'flex';
}

function selectMod(el) {
  var mod = el.dataset.mod;
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
  var container = document.getElementById(containerId);
  if (!container) return;

  var overall = result.overall_oligovoid_score || 0;
  var scoreColor = scoreColorFn(overall);

  container.innerHTML =
    '<h4 style="color:var(--accent-cyan);">Full Analysis</h4>' +
    '<div style="display:flex;align-items:baseline;gap:0.6rem;margin:0.5rem 0;">' +
      '<span class="mono" style="font-size:1.8rem;font-weight:700;color:' + scoreColor + '">' + overall.toFixed(1) + '</span>' +
      '<span style="color:var(--text-secondary);font-size:0.75rem;">/100 OligoVoid Score</span>' +
    '</div>' +
    '<div class="score-bars" style="margin:0.6rem 0;">' +
      [
        { label: 'Thermodynamic', val: result.thermodynamic_score },
        { label: 'RISC Loading', val: result.risc_loading_score },
        { label: 'Nuclease Resistance', val: result.nuclease_resistance_score },
        { label: 'Off-Target', val: result.off_target_risk_score ? (100 - result.off_target_risk_score) : null },
      ].map(function(b) {
        if (b.val == null) return '';
        var cls = b.val >= 75 ? 'bg-score-high' : b.val >= 50 ? 'bg-score-mid' : 'bg-score-low';
        return '<div class="score-bar-item">' +
          '<div class="score-bar-top"><span class="score-bar-label">' + b.label + '</span><span class="score-bar-value" style="color:' + scoreColorFn(b.val) + '">' + b.val.toFixed(0) + '</span></div>' +
          '<div class="score-bar-track"><div class="score-bar-fill ' + cls + '" style="width:' + b.val + '%"></div></div>' +
        '</div>';
      }).join('') +
    '</div>' +
    (result.classification ? '<div class="void-badges" style="margin-top:0.5rem;"><span class="void-badge type-badge">' + formatVoidType(result.classification.void_type || '') + '</span></div>' : '');
}

// ═══════════════════════════════════════════════════════
// TAB 7: AI GENERATED (CVAE)
// ═══════════════════════════════════════════════════════

function initGenerativeTab() {
  if (generativeInitialized) return;
  generativeInitialized = true;

  var efficacySlider = document.getElementById('gen-efficacy');
  var tempSlider = document.getElementById('gen-temp');
  var countSlider = document.getElementById('gen-count');

  if (efficacySlider) {
    efficacySlider.addEventListener('input', function() {
      document.getElementById('gen-efficacy-value').textContent = efficacySlider.value;
    });
  }
  if (tempSlider) {
    tempSlider.addEventListener('input', function() {
      document.getElementById('gen-temp-value').textContent = parseFloat(tempSlider.value).toFixed(1);
    });
  }
  if (countSlider) {
    countSlider.addEventListener('input', function() {
      document.getElementById('gen-count-value').textContent = countSlider.value;
    });
  }

  var btn = document.getElementById('btn-generate');
  if (btn) btn.addEventListener('click', runGeneration);
}

async function runGeneration() {
  var efficacy = parseFloat(document.getElementById('gen-efficacy').value);
  var temp = parseFloat(document.getElementById('gen-temp').value);
  var count = parseInt(document.getElementById('gen-count').value);

  var loading = document.getElementById('gen-loading');
  var results = document.getElementById('gen-results');
  var noteEl = document.getElementById('gen-model-note');

  loading.style.display = 'flex';
  results.style.display = 'none';
  noteEl.style.display = 'none';

  try {
    var data = await apiFetch('/api/generate/candidates', {
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
    unlockAchievement('generator');
  } catch (err) {
    loading.style.display = 'none';
    showToast('Generation failed: ' + err.message, true);
  }
}

function renderGeneratedCandidates(data) {
  var results = document.getElementById('gen-results');
  var cardsEl = document.getElementById('gen-cards');
  var noteEl = document.getElementById('gen-model-note');

  results.style.display = 'block';

  if (!data.candidates || data.candidates.length === 0) {
    cardsEl.innerHTML = '<div class="no-data">No valid candidates generated. Try adjusting temperature.</div>';
    return;
  }

  cardsEl.innerHTML = data.candidates.map(function(cand, idx) {
    var pred = cand.predicted_efficacy || 0;
    var unc = cand.uncertainty_std || 0;
    var conf = cand.model_confidence || 'low';
    var confClass = conf === 'high' ? 'high' : conf === 'medium' ? 'medium' : 'low';
    var isNovel = cand.is_novel;

    var patternHtml = renderFeatureBlocks(cand.feature_vector_original || []);

    return '<div class="gen-card">' +
      '<div class="gen-card-header">' +
        '<span class="gen-card-rank">#' + (cand.rank || idx + 1) + '</span>' +
        (isNovel
          ? '<span class="gen-card-badge novel">Novel</span>'
          : '<span class="gen-card-badge void">Near Known</span>') +
      '</div>' +
      '<div class="gen-card-pattern">' + patternHtml + '</div>' +
      '<div class="gen-card-stats">' +
        '<div class="gen-stat"><span class="gen-stat-label">Predicted efficacy</span><span class="gen-stat-value ' + confClass + '">' + pred.toFixed(0) + '% knockdown</span></div>' +
        '<div class="gen-stat"><span class="gen-stat-label">Uncertainty</span><span class="gen-stat-value">&plusmn;' + unc.toFixed(0) + '% (' + conf + ' confidence)</span></div>' +
        '<div class="gen-stat"><span class="gen-stat-label">Extrapolation</span><span class="gen-stat-value">' + (cand.is_extrapolation ? 'Yes — novel chemistry' : 'No — within training range') + '</span></div>' +
        '<div class="gen-stat"><span class="gen-stat-label">Target</span><span class="gen-stat-value">' + cand.target_efficacy_pct + '% at temp ' + cand.temperature + '</span></div>' +
      '</div>' +
    '</div>';
  }).join('');

  if (data.gp_model_note) {
    noteEl.textContent = data.gp_model_note;
    noteEl.style.display = 'block';
  }
}

function renderFeatureBlocks(features) {
  var colors = ['#3b82f6', '#22c55e', '#ef4444', '#f97316', '#a78bfa', '#8892b0', '#ec4899', '#f59e0b'];
  var blocks = [];
  var nBlocks = Math.min(21, features.length);
  for (var i = 0; i < nBlocks; i++) {
    var val = features[i] || 0;
    var absVal = Math.min(Math.abs(val), 3);
    var colorIdx = Math.floor((absVal / 3) * (colors.length - 1));
    var color = colors[Math.min(colorIdx, colors.length - 1)];
    var opacity = 0.4 + (absVal / 3) * 0.6;
    blocks.push(
      '<div class="gen-mod-block" style="background:' + color + ';opacity:' + opacity.toFixed(2) + '" title="Feature ' + (i+1) + ': ' + val.toFixed(2) + '"></div>'
    );
  }
  for (var i = nBlocks; i < 21; i++) {
    blocks.push('<div class="gen-mod-block" style="background:#8892b0;opacity:0.3"></div>');
  }
  return blocks.join('');
}

// ═══════════════════════════════════════════════════════
// TAB 8: CASE STUDY
// ═══════════════════════════════════════════════════════

async function loadCaseStudy() {
  if (caseStudyLoaded) return;
  var loading = document.getElementById('case-loading');
  if (loading) loading.style.display = 'flex';

  try {
    var data = await apiFetch('/api/casestudy');
    renderCaseStudy(data);
    caseStudyLoaded = true;
  } catch (err) {
    showToast('Failed to load case study: ' + err.message, true);
  } finally {
    if (loading) loading.style.display = 'none';
  }
}

function renderCaseStudy(data) {
  var exec = document.getElementById('case-executive');
  if (exec) {
    exec.innerHTML =
      '<div style="font-size:0.8rem;color:var(--accent-biolum);font-family:var(--font-mono);margin-bottom:0.5rem">' +
        'OLIGOVOID SCORE: ' + (data.overall_oligovoid_score || '?') + '/100' +
        ' &mdash; Recommendation: ' + (data.overall_recommendation || '?') +
      '</div>' +
      '<p>' + (data.executive_summary || '') + '</p>';
  }

  var diffEl = document.getElementById('case-difference-content');
  if (diffEl) diffEl.innerHTML = '<p>' + (data.what_is_different || '') + '</p>';

  var riskEl = document.getElementById('case-risk-cards');
  if (riskEl && data.risk_assessment) {
    riskEl.innerHTML = data.risk_assessment.map(function(r) {
      var cls = r.traffic_light === 'green' ? 'risk-green' : r.traffic_light === 'yellow' ? 'risk-yellow' : 'risk-red';
      var icon = r.traffic_light === 'green' ? '&#x1f7e2;' : r.traffic_light === 'yellow' ? '&#x1f7e1;' : '&#x1f534;';
      return '<div class="case-risk-card ' + cls + '">' +
        '<div class="case-risk-dim">' + icon + ' ' + r.dimension + ' <span class="case-risk-score">' + r.score + '/100 &mdash; ' + r.adjective + '</span></div>' +
        '<div class="case-risk-plain">' + r.plain_english + '</div>' +
      '</div>';
    }).join('');
  }

  var hypEl = document.getElementById('case-hypothesis-content');
  if (hypEl && data.hypothesis) {
    hypEl.innerHTML =
      '<p><strong>If it works:</strong> ' + data.hypothesis.if_it_works + '</p>' +
      '<p><strong>If it fails:</strong> ' + data.hypothesis.if_it_fails + '</p>' +
      '<p style="margin-top:0.5rem"><strong>Fastest experiment:</strong> ' + data.hypothesis.fastest_experiment + '</p>';
  }

  var closestEl = document.getElementById('case-closest-content');
  if (closestEl && data.closest_fda_drug) {
    var c = data.closest_fda_drug;
    closestEl.innerHTML =
      '<p>The most similar FDA-approved drug is <strong>' + c.drug_name + '</strong> (' + (c.brand || '') + ').</p>' +
      '<p>Similarity: ' + c.similarity_positions + '/' + c.total_positions + ' positions identical (' + c.similarity_pct + '%).</p>' +
      '<p>Their clinical efficacy: ' + c.their_efficacy + '%.</p>' +
      '<p>Estimated probability this void achieves &gt;70%: <strong>' + c.estimated_success_probability + '%</strong></p>' +
      '<p style="font-size:0.85rem;color:var(--text-secondary);margin-top:0.5rem">' + c.probability_basis + '</p>';
  }

  var recEl = document.getElementById('case-recommendation');
  if (recEl) {
    var recClass = data.overall_recommendation === 'PRIORITIZE' ? 'case-rec-prioritize'
      : data.overall_recommendation === 'INVESTIGATE' ? 'case-rec-investigate' : 'case-rec-low';
    recEl.className = 'case-recommendation ' + recClass;
    recEl.innerHTML =
      '<h3>Recommendation: ' + (data.overall_recommendation || '?') + '</h3>' +
      '<p>' + (data.recommendation_plain_english || '') + '</p>';
  }
}

// ═══════════════════════════════════════════════════════
// TOAST NOTIFICATIONS
// ═══════════════════════════════════════════════════════

function showToast(msg, isError) {
  var container = document.getElementById('toast-container');
  var toast = document.createElement('div');
  toast.className = 'toast' + (isError ? ' error' : '');
  toast.textContent = msg;
  container.appendChild(toast);

  requestAnimationFrame(function() { toast.classList.add('show'); });

  setTimeout(function() {
    toast.classList.remove('show');
    setTimeout(function() { toast.remove(); }, 300);
  }, 3500);
}

// ═══════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════

function truncate(str, max) {
  if (str.length <= max) return str;
  return str.slice(0, max) + '...';
}

// Make globally accessible for inline onclick handlers
window.toggleVoidExpand = toggleVoidExpand;
window.selectMod = selectMod;
