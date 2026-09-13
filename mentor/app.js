/* Second Voice — a mentor that answers the sentence in your head.
   No build step, no server, no account. State lives in this browser. */

(function () {
  "use strict";

  // ---------- storage (never throw; a private window must still work) ----------
  var MEM = {};
  function load(key, fallback) {
    try {
      var raw = localStorage.getItem("sv." + key);
      return raw ? JSON.parse(raw) : (MEM[key] !== undefined ? MEM[key] : fallback);
    } catch (e) { return MEM[key] !== undefined ? MEM[key] : fallback; }
  }
  function save(key, val) {
    MEM[key] = val;
    try { localStorage.setItem("sv." + key, JSON.stringify(val)); } catch (e) {}
  }

  var state = {
    blocks: load("blocks", []),
    log: load("log", []),
    budget: load("budget", 3),
    lastAnswer: null,
    rejected: []
  };

  // ---------- corpus ----------
  var CORPUS = (typeof window.SV_CORPUS !== "undefined") ? window.SV_CORPUS : null;

  // ---------- matching (see match.js; separated so it can be tested headless) ----------
  var INDEX = null;
  function buildIndex() { INDEX = new SVMatch.Index(CORPUS.entries); }

  function entryById(id) {
    for (var i = 0; i < CORPUS.entries.length; i++) if (CORPUS.entries[i].id === id) return CORPUS.entries[i];
    return null;
  }

  function bestFor(query, exclude) {
    if (!INDEX) buildIndex();
    var hit = INDEX.best(query, exclude);
    return { entry: entryById(hit.id), score: hit.score };
  }

  // ---------- helpers ----------
  var $ = function (s) { return document.querySelector(s); };
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function todayKey() { var d = new Date(); return d.getFullYear() + "-" + (d.getMonth() + 1) + "-" + d.getDate(); }
  function nowMins() { var d = new Date(); return d.getHours() * 60 + d.getMinutes(); }
  function toMins(hhmm) { var p = String(hhmm).split(":"); return (+p[0]) * 60 + (+p[1]); }
  function fmtTime(hhmm) { return hhmm; }
  function fmtWhen(ts) {
    var d = new Date(ts), now = new Date();
    var t = String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
    if (d.toDateString() === now.toDateString()) return "today " + t;
    return (d.getMonth() + 1) + "/" + d.getDate() + " " + t;
  }

  // ---------- tabs ----------
  function showTab(name) {
    ["day", "stuck", "log"].forEach(function (t) {
      $("#tab-" + t).setAttribute("aria-selected", String(t === name));
      $("#panel-" + t).hidden = (t !== name);
    });
    if (name === "log") renderLog();
    if (name === "day") renderDay();
  }

  // ---------- day ----------
  function renderDay() {
    var list = $("#blocks"); list.innerHTML = "";
    var blocks = state.blocks.slice().sort(function (a, b) { return toMins(a.time) - toMins(b.time); });
    if (!blocks.length) {
      list.appendChild(el("div", "faint", "No blocks yet. Add the two or three that actually matter today — not everything."));
    }
    var cur = nowMins(), nextIdx = -1;
    for (var i = 0; i < blocks.length; i++) { if (toMins(blocks[i].time) >= cur) { nextIdx = i; break; } }

    blocks.forEach(function (b, i) {
      var st = (b.status && b.status[todayKey()]) || null;
      var row = el("div", "block" + (i === nextIdx ? " now" : "") + (st === "did" ? " done" : ""));
      row.appendChild(el("div", "t", fmtTime(b.time)));
      var body = el("div", "body");
      body.appendChild(el("div", "what", b.what));
      if (b.why) body.appendChild(el("div", "why", "because " + b.why));
      var acts = el("div", "acts");
      if (st) {
        acts.appendChild(el("span", "pill " + (st === "did" ? "good" : "bad"), st === "did" ? "done" : "skipped"));
      } else {
        var yes = el("button", "btn sm good", "Did it");
        yes.onclick = function () { setStatus(b, "did"); };
        var no = el("button", "btn sm bad", "Didn't");
        no.onclick = function () { setStatus(b, "skip"); openStuck(b); };
        acts.appendChild(yes); acts.appendChild(no);
      }
      var del = el("button", "btn sm ghost", "remove");
      del.onclick = function () {
        state.blocks = state.blocks.filter(function (x) { return x.id !== b.id; });
        save("blocks", state.blocks); renderDay();
      };
      acts.appendChild(del);
      body.appendChild(acts);
      row.appendChild(body);
      list.appendChild(row);
    });

    $("#budget-used").textContent = promptsUsedToday() + " / " + state.budget;
  }

  function setStatus(b, st) {
    b.status = b.status || {};
    b.status[todayKey()] = st;
    save("blocks", state.blocks);
    renderDay();
  }

  function addBlock(time, what, why) {
    state.blocks.push({ id: "b" + Date.now(), time: time, what: what, why: why, status: {} });
    save("blocks", state.blocks);
    renderDay();
    scheduleAll();
  }

  // ---------- stuck ----------
  // Design note: purely lexical matching of a freely typed sentence scores 2/15
  // top-1 on a held-out set (see test_match.js). People describe a situation,
  // not the belief under it. So typing FILTERS a browsable list rather than
  // asserting an answer, and the choice is always the user's.
  var stuckContext = null;

  function openStuck(block) {
    stuckContext = block || null;
    showTab("stuck");
    $("#stuck-for").textContent = block ? ("You skipped: " + block.what) : "";
    $("#stuck-for").hidden = !block;
    $("#belief").focus();
  }

  function renderCandidates() {
    var q = $("#belief").value.trim();
    var box = $("#chips"); box.innerHTML = "";
    var ids;
    if (q.length >= 3) {
      if (!INDEX) buildIndex();
      ids = INDEX.rank(q).slice(0, 6).map(function (r) { return r.id; });
      $("#chips-lab").textContent = "Closest matches — pick the one that is actually true:";
    } else {
      var mine = topBeliefs().slice(0, 3).map(function (r) { return r.id; });
      var rest = CORPUS.entries.map(function (e) { return e.id; });
      ids = mine.concat(rest);
      $("#chips-lab").textContent = mine.length
        ? "Yours most often, then the rest:"
        : "Or pick the one that is actually true:";
    }
    var seen = {};
    ids.forEach(function (id) {
      if (seen[id]) return; seen[id] = 1;
      var e = entryById(id);
      var b = el("button", null, e.belief);
      b.onclick = function () { answerWith(e.id, q || e.belief); };
      box.appendChild(b);
    });
  }

  function answerWith(id, query) {
    var e = entryById(id);
    if (!e) return;
    state.lastAnswer = { query: query, id: id, ts: Date.now() };
    renderAnswer(e, query);
    logEvent({
      kind: "stuck", ts: Date.now(), query: query, matched: e.id,
      belief: e.belief, block: stuckContext ? stuckContext.what : null, moveDone: null
    });
    $("#answer").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderAnswer(e, query) {
    var box = $("#answer");
    box.innerHTML = "";
    box.className = "card answer";
    box.hidden = false;

    if (query && query !== e.belief) box.appendChild(el("div", "belief", "You wrote: “" + query + "”"));
    box.appendChild(el("div", "belief", e.belief));

    var bq = el("blockquote"); bq.textContent = "“" + e.quote + "”";
    box.appendChild(bq);

    var who = el("div", "who");
    who.appendChild(el("b", null, e.who));
    var badgeCls = e.attribution.indexOf("misattributed") === 0 ? "m"
      : (e.attribution.indexOf("commonly") === 0 ? "c" : "v");
    var badgeTxt = badgeCls === "m" ? "check the source" : (badgeCls === "c" ? "commonly attributed" : "verified");
    who.appendChild(el("span", "badge " + badgeCls, badgeTxt));
    box.appendChild(who);
    box.appendChild(el("div", "src", e.source + (badgeCls !== "v" ? " — " + e.attribution : "")));

    box.appendChild(el("hr"));
    box.appendChild(el("div", "refute", e.refutation));

    var mv = el("div", "move");
    mv.appendChild(el("div", "lab", "Smaller version — do this instead"));
    mv.appendChild(el("div", null, e.move));
    box.appendChild(mv);

    var acts = el("div", "row"); acts.style.marginTop = "14px";
    var did = el("button", "btn primary", "Did the smaller version");
    did.onclick = function () { markMove(true); };
    var nope = el("button", "btn", "Still didn't");
    nope.onclick = function () { markMove(false); };
    acts.appendChild(did); acts.appendChild(nope);
    box.appendChild(acts);
  }

  function markMove(done) {
    for (var i = state.log.length - 1; i >= 0; i--) {
      if (state.log[i].kind === "stuck" && state.log[i].moveDone === null) {
        state.log[i].moveDone = done; break;
      }
    }
    save("log", state.log);
    $("#answer").hidden = true;
    $("#belief").value = "";
    renderCandidates();
    showTab("log");
  }

  function logEvent(ev) { state.log.push(ev); save("log", state.log); }

  // ---------- log ----------
  function topBeliefs() {
    var counts = {};
    state.log.forEach(function (e) {
      if (e.kind !== "stuck") return;
      counts[e.matched] = counts[e.matched] || { id: e.matched, belief: e.belief, n: 0, beat: 0 };
      counts[e.matched].n++;
      if (e.moveDone === true) counts[e.matched].beat++;
    });
    return Object.keys(counts).map(function (k) { return counts[k]; })
      .sort(function (a, b) { return b.n - a.n; });
  }

  function renderLog() {
    var top = topBeliefs();
    var tb = $("#topbeliefs"); tb.innerHTML = "";
    if (!top.length) {
      tb.appendChild(el("div", "faint", "Nothing logged yet. After a week this is the part that matters: the same two or three sentences will be responsible for most of what you did not do."));
    }
    var max = top.length ? top[0].n : 1;
    top.slice(0, 6).forEach(function (r) {
      var row = el("div"); row.style.marginBottom = "12px";
      var head = el("div", "rank");
      head.appendChild(el("span", null, r.belief));
      head.appendChild(el("span", "faint", r.n + "× · beat it " + r.beat + "×"));
      row.appendChild(head);
      var bar = el("div", "bar"); var fill = el("i");
      fill.style.width = Math.round(100 * r.n / max) + "%";
      bar.appendChild(fill); row.appendChild(bar);
      tb.appendChild(row);
    });

    var lg = $("#logrows"); lg.innerHTML = "";
    state.log.slice().reverse().slice(0, 40).forEach(function (e) {
      var row = el("div", "logrow");
      row.appendChild(el("div", "when", fmtWhen(e.ts)));
      var body = el("div"); body.style.flex = "1";
      body.appendChild(el("div", null, "“" + e.query + "”"));
      var meta = e.belief + (e.block ? " · skipped: " + e.block : "");
      body.appendChild(el("div", "faint", meta));
      row.appendChild(body);
      var st = e.moveDone === true ? "pill good" : (e.moveDone === false ? "pill bad" : "pill");
      row.appendChild(el("span", st, e.moveDone === true ? "beat" : (e.moveDone === false ? "lost" : "open")));
      lg.appendChild(row);
    });
  }

  // ---------- notifications (honest about what a web app can do) ----------
  var timers = [];
  function promptsUsedToday() {
    var k = todayKey();
    return (load("fired", {})[k] || []).length;
  }
  function noteFired(id) {
    var f = load("fired", {}), k = todayKey();
    f[k] = (f[k] || []).concat([id]);
    save("fired", f);
  }

  function scheduleAll() {
    timers.forEach(clearTimeout); timers = [];
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    var cur = nowMins();
    state.blocks.forEach(function (b) {
      var delta = toMins(b.time) - cur;
      if (delta <= 0 || delta > 720) return;
      timers.push(setTimeout(function () {
        if (promptsUsedToday() >= state.budget) return;   // interruption budget
        if (b.status && b.status[todayKey()]) return;      // already resolved
        noteFired(b.id);
        try {
          new Notification(b.what, {
            body: b.why ? "because " + b.why : "Open when you get a second.",
            tag: b.id
          });
        } catch (err) {}
      }, delta * 60000));
    });
  }

  function requestNotifs() {
    if (!("Notification" in window)) { $("#notif-state").textContent = "This browser has no notification support."; return; }
    Notification.requestPermission().then(function (p) {
      $("#notif-state").textContent = p === "granted"
        ? "On — but only while this page is open. See the note below."
        : "Blocked or dismissed.";
      if (p === "granted") scheduleAll();
    });
  }

  // ---------- boot ----------
  function boot() {
    buildIndex();
    renderCandidates();
    renderDay();

    $("#tab-day").onclick = function () { showTab("day"); };
    $("#tab-stuck").onclick = function () { showTab("stuck"); };
    $("#tab-log").onclick = function () { showTab("log"); };

    $("#add").onsubmit = function (ev) {
      ev.preventDefault();
      var t = $("#f-time").value, w = $("#f-what").value.trim(), y = $("#f-why").value.trim();
      if (!t || !w) return;
      addBlock(t, w, y);
      $("#f-what").value = ""; $("#f-why").value = "";
    };

    $("#belief").addEventListener("input", renderCandidates);

    $("#enable-notifs").onclick = requestNotifs;
    if ("Notification" in window && Notification.permission === "granted") {
      $("#notif-state").textContent = "On — but only while this page is open.";
      scheduleAll();
    }

    $("#export").onclick = function () {
      var data = JSON.stringify({ blocks: state.blocks, log: state.log }, null, 2);
      $("#exportbox").value = data;
      $("#exportbox").hidden = false;
      $("#exportbox").select();
    };

    $("#budget").value = state.budget;
    $("#budget").onchange = function () {
      state.budget = +$("#budget").value; save("budget", state.budget); renderDay(); scheduleAll();
    };

    showTab(state.blocks.length ? "day" : "day");
  }

  if (CORPUS) { boot(); }
  else {
    fetch("corpus.json").then(function (r) { return r.json(); })
      .then(function (c) { CORPUS = c; boot(); })
      .catch(function () { document.body.innerHTML = "<p style='padding:20px'>Could not load corpus.json. Serve this folder over http, not file://</p>"; });
  }
})();
