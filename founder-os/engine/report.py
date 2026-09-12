"""Render a cycle into a standalone HTML report.

The report is the deliverable. It has to show its own working: every ranking
carries the gate verdicts that produced it, every claim carries its citation,
and every idea carries the conditions that would prove it wrong plus the
cheapest test that would settle it.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from store import Store

CSS = """
:root{--ground:#f6f7f9;--surface:#fff;--surface-2:#eef1f5;--hairline:#dde2e9;
--hairline-strong:#c3ccd8;--ink:#0f141b;--ink-2:#38424f;--muted:#5f6a7a;
--signal:#00854b;--signal-dim:#d3f0e0;--void:#5340cc;--void-dim:#e2ddfb;
--kill:#c32b38;--kill-dim:#fadfe2;--warn:#8a5d00;
--mono:"Space Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
--sans:"Inter",system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
--ground:#0d0f14;--surface:#141922;--surface-2:#1b212c;--hairline:#242c39;
--hairline-strong:#36404f;--ink:#e8edf4;--ink-2:#c2cbd8;--muted:#8d99ab;
--signal:#00ff88;--signal-dim:#0d2a1e;--void:#9a8bff;--void-dim:#1e1b38;
--kill:#ff6b76;--kill-dim:#331519;--warn:#f5b544}}
:root[data-theme="dark"]{--ground:#0d0f14;--surface:#141922;--surface-2:#1b212c;
--hairline:#242c39;--hairline-strong:#36404f;--ink:#e8edf4;--ink-2:#c2cbd8;
--muted:#8d99ab;--signal:#00ff88;--signal-dim:#0d2a1e;--void:#9a8bff;
--void-dim:#1e1b38;--kill:#ff6b76;--kill-dim:#331519;--warn:#f5b544}
*{box-sizing:border-box}
body{background:var(--ground);color:var(--ink);font-family:var(--sans);
font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased}
.wrap{max-width:1000px;margin:0 auto;padding-inline:20px;padding-block:0 80px}
h1,h2,h3{text-wrap:balance;line-height:1.2;margin:0}
h1{font-size:clamp(1.9rem,5vw,2.8rem);font-weight:700;letter-spacing:-.025em}
h2{font-size:clamp(1.25rem,3vw,1.6rem);font-weight:650;letter-spacing:-.015em}
h3{font-size:1.05rem;font-weight:650}
p{margin:0}
.col{max-width:70ch}
.eyebrow{font-family:var(--mono);font-size:.67rem;font-weight:700;
letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
.lede{font-size:1.08rem;color:var(--ink-2);max-width:64ch}
.fine{font-size:.85rem;color:var(--muted)}
header.mast{border-bottom:1px solid var(--hairline);padding-block:50px 30px;
display:flex;flex-direction:column;gap:16px}
section{padding-block:38px;border-bottom:1px solid var(--hairline)}
section:last-of-type{border-bottom:0}
.shead{display:flex;flex-direction:column;gap:8px;margin-bottom:22px}
.meta{display:flex;flex-wrap:wrap;gap:8px 24px;font-family:var(--mono);
font-size:.75rem;color:var(--muted)}
.tscroll{overflow-x:auto;border:1px solid var(--hairline);border-radius:3px;
background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:.88rem}
th,td{text-align:left;padding:10px 13px;border-bottom:1px solid var(--hairline);
vertical-align:top}
thead th{font-family:var(--mono);font-size:.66rem;font-weight:700;
letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
background:var(--surface-2);white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
.funnel{display:flex;flex-direction:column;gap:3px}
.rung{display:grid;grid-template-columns:46px minmax(0,1fr) 92px;gap:5px 12px;
align-items:center}
.rung .g{font-family:var(--mono);font-weight:700;font-size:.8rem;color:var(--muted)}
.rung .bar{background:var(--surface-2);border:1px solid var(--hairline);
border-radius:2px;padding:8px 12px;font-size:.87rem;color:var(--ink);
font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rung .k{font-family:var(--mono);font-size:.76rem;color:var(--kill);
text-align:right;font-variant-numeric:tabular-nums}
.rung.alive .bar{background:var(--signal-dim);border-color:var(--signal)}
.rung.alive .k{color:var(--signal)}
.card{background:var(--surface);border:1px solid var(--hairline-strong);
border-radius:3px;padding:22px 24px;display:flex;flex-direction:column;gap:14px;
margin-bottom:18px}
.card.top{border-left:3px solid var(--signal)}
.chead{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:baseline;
justify-content:space-between}
.rank{font-family:var(--mono);font-size:.72rem;font-weight:700;
letter-spacing:.1em;color:var(--void);text-transform:uppercase}
.score{font-family:var(--mono);font-weight:700;font-size:1.35rem;color:var(--ink);
font-variant-numeric:tabular-nums}
.heads{display:flex;flex-wrap:wrap;gap:6px 18px;font-family:var(--mono);
font-size:.74rem;color:var(--muted)}
.heads b{color:var(--ink)}
.kv{display:grid;grid-template-columns:118px minmax(0,1fr);gap:5px 14px;
font-size:.92rem}
.kv dt{font-family:var(--mono);font-size:.72rem;letter-spacing:.06em;
text-transform:uppercase;color:var(--muted);padding-top:3px}
.kv dd{margin:0;color:var(--ink-2)}
.pill{display:inline-block;font-family:var(--mono);font-size:.68rem;
padding:2px 7px;border-radius:2px;background:var(--surface-2);
border:1px solid var(--hairline);color:var(--muted);margin-right:5px}
.pill.ok{background:var(--signal-dim);border-color:var(--signal);color:var(--signal)}
.pill.bad{background:var(--kill-dim);border-color:var(--kill);color:var(--kill)}
.pill.vd{background:var(--void-dim);border-color:var(--void);color:var(--void)}
details{border-top:1px solid var(--hairline);padding-top:11px}
summary{cursor:pointer;font-family:var(--mono);font-size:.75rem;
letter-spacing:.05em;color:var(--muted)}
summary:focus-visible{outline:2px solid var(--signal);outline-offset:2px}
.atk{display:grid;grid-template-columns:150px minmax(0,1fr);gap:6px 14px;
font-size:.88rem;margin-top:11px}
.atk dt{font-family:var(--mono);font-size:.72rem;color:var(--muted)}
.atk dd{margin:0;color:var(--ink-2)}
ul.tight{margin:0;padding-left:1.1rem;display:flex;flex-direction:column;gap:5px}
ul.tight li{font-size:.9rem;color:var(--ink-2)}
.note{border-left:2px solid var(--hairline-strong);padding-left:15px;
color:var(--muted);font-size:.9rem}
a{color:var(--signal);text-underline-offset:2px}
footer{padding-block:32px;color:var(--muted);font-size:.85rem;
display:flex;flex-direction:column;gap:7px}
@media (max-width:620px){.kv{grid-template-columns:1fr}.atk{grid-template-columns:1fr}
.rung{grid-template-columns:40px minmax(0,1fr) 76px}}
"""


def esc(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def render(store: Store, cycle_id: int, out_path: str | Path,
           title: str = "Founder OS Report") -> Path:
    cycle = store.cycle(cycle_id) or {}
    all_ideas = store.ideas(cycle_id=cycle_id)
    alive = [i for i in all_ideas if i["status"] != "killed"]
    killed = [i for i in all_ideas if i["status"] == "killed"]

    ranked = []
    for i in alive:
        sc = store.scores(i["id"]) or {}
        ranked.append({**i, "sc": sc})
    ranked.sort(key=lambda r: (r["sc"].get("founder_score") or 0), reverse=True)

    sig_by_id = {s["id"]: s for s in store.signals()}
    parts: list[str] = []

    # ---- masthead ----
    parts.append(f"""<header class="mast">
<div class="eyebrow">Cycle {esc(cycle_id)} &middot; {esc(cycle.get('started_at',''))}</div>
<h1>{esc(title)}</h1>
<p class="lede">{len(all_ideas)} candidates generated across {len(set(i['island'] for i in all_ideas))}
island theses. {len(killed)} killed by the gates. {len(alive)} survived to ranking.</p>
<div class="meta">
<span>evidence: {len(sig_by_id)} signals</span>
<span>corpus: {len(store.products())} products</span>
<span>weights: {esc((ranked[0]['sc'].get('weights_version') if ranked else 'n/a'))}</span>
<span>uncalibrated &mdash; ranking is internally consistent, not backtested</span>
</div></header>""")

    # ---- attrition ----
    parts.append(_funnel(all_ideas, killed, alive))

    # ---- dossiers ----
    parts.append('<section><div class="shead"><div class="eyebrow">Survivors</div>'
                 '<h2>What lived, and why</h2><p class="col">Ranked by the harmonic '
                 'composite. Both heads are shown separately, because collapsing '
                 'novelty and viability into one number is where the '
                 'ideation-execution gap hides.</p></div>')
    if not ranked:
        parts.append('<p class="note">Nothing survived the ladder this cycle. '
                     'That is a real result, not a failure: it means the gates '
                     'are biting. The kill log below says where.</p>')
    for n, r in enumerate(ranked, 1):
        parts.append(_dossier(store, r, n, sig_by_id))
    parts.append("</section>")

    # ---- kill log ----
    parts.append(_kill_log(killed))

    # ---- evidence ----
    parts.append(_evidence(sig_by_id))

    parts.append(f"""<footer>
<p>Generated by the Founder OS engine. Every ranking above is reproducible from
the run ledger in the cycle store.</p>
<p class="fine">Uncalibrated: the scorer has not yet been backtested against
labelled historical outcomes. Published benchmarks on this class of prediction
top out near a 4.7x lift over a sub-1% base rate. Treat this as a ranked
shortlist with kill conditions, never as a verdict.</p></footer>""")

    doc = (f"<title>{esc(title)}</title>\n"
           '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
           'family=Inter:wght@400;500;600;700&family=Space+Mono:wght@400;700'
           '&display=swap">\n'
           f"<style>{CSS}</style>\n"
           f'<div class="wrap">{"".join(parts)}</div>')

    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc)
    return p


def _funnel(all_ideas, killed, alive) -> str:
    by_gate: dict[str, int] = {}
    for k in killed:
        by_gate[k["killed_at_gate"] or "?"] = by_gate.get(k["killed_at_gate"] or "?", 0) + 1
    total = max(1, len(all_ideas))
    rows, remaining = [], len(all_ideas)
    labels = {"L0": "Validity", "L1": "Obviousness", "L2": "Grounding",
              "L3": "Buildability", "L4": "Adversarial panel"}
    rows.append(("in", "Generated", 100.0, f"{len(all_ideas)}"))
    for g in ("L0", "L1", "L2", "L3", "L4"):
        n = by_gate.get(g, 0)
        remaining -= n
        rows.append((g, labels[g], 100.0 * remaining / total,
                     f"-{n}" if n else "0"))
    rows.append(("L5", "Ranked", 100.0 * len(alive) / total, f"{len(alive)}"))

    bars = "".join(
        f'<div class="rung{" alive" if g in ("L5", "in") else ""}">'
        f'<span class="g">{esc(g)}</span>'
        f'<div class="bar" style="width:{max(14.0, w):.0f}%">{esc(lbl)}</div>'
        f'<span class="k">{esc(k)}</span></div>'
        for g, lbl, w, k in rows)

    return (f'<section><div class="shead"><div class="eyebrow">Attrition</div>'
            f'<h2>Where the candidates died</h2>'
            f'<p class="col">Every gate must kill. A gate that passes almost '
            f'everything is decoration and gets removed.</p></div>'
            f'<div class="funnel">{bars}</div></section>')


def _dossier(store: Store, r: dict, n: int, sig_by_id: dict) -> str:
    g = json.loads(r["genome"])
    sc = r["sc"]
    v = {x["gate"]: x for x in store.verdicts(r["id"])}
    l1 = (v.get("L1", {}).get("detail") or {}).get("detail", {})
    l3 = (v.get("L3", {}).get("detail") or {}).get("detail", {})
    l4 = (v.get("L4", {}).get("detail") or {}).get("detail", {})
    notes = g.get("notes") or {}

    def sv(k: str) -> str:
        x = g.get(k)
        return esc(x.get("value") if isinstance(x, dict) else x)

    cites = []
    for k in ("unlock", "pain"):
        slot = g.get(k) or {}
        for sid in (slot.get("signal_ids") or []):
            s = sig_by_id.get(sid)
            if s:
                cites.append(f'<a href="{esc(s["source_url"])}">[{sid}] '
                             f'{esc(s["title"][:70])}</a>')

    attacks = ""
    if l4.get("attacks"):
        items = "".join(
            f'<dt>{esc(a.get("surface", "?"))} '
            f'<span class="pill {_vp(a.get("verdict"))}">{esc(a.get("verdict", "?"))}</span></dt>'
            f'<dd>{esc(a.get("attack", ""))[:400]}'
            f'{"<br><em>defence:</em> " + esc(a.get("strongest_defence", ""))[:260] if a.get("strongest_defence") else ""}</dd>'
            for a in l4["attacks"])
        attacks = (f'<details><summary>The panel&rsquo;s attacks '
                   f'({l4.get("n_counted", 0)} counted, '
                   f'{l4.get("n_abstain", 0)} abstained)</summary>'
                   f'<dl class="atk">{items}</dl></details>')

    kills = "".join(f"<li>{esc(k)}</li>" for k in (g.get("kill") or []))
    miles = "".join(f"<li>{esc(m)}</li>" for m in (l3.get("milestones") or []))

    econ_pill = ("ok" if (l3.get("margin_ratio") or 0) > 0.3 else "bad")

    return f"""<article class="card{' top' if n <= 3 else ''}">
<div class="chead">
  <div><span class="rank">#{n} &middot; island {esc(r['island'])} &middot; {esc(r['operator'])}</span>
  <h3>{esc(g.get('title'))}</h3></div>
  <div style="text-align:right">
    <div class="score">{esc(sc.get('founder_score'))}</div>
    <div class="heads"><span>novelty <b>{esc(sc.get('novelty'))}</b></span>
    <span>viability <b>{esc(sc.get('viability'))}</b></span></div>
  </div>
</div>
<dl class="kv">
  <dt>for whom</dt><dd>{sv('audience')}</dd>
  <dt>the problem</dt><dd>{sv('pain')}</dd>
  <dt>why now</dt><dd>{esc(notes.get('why_now', ''))} <span class="pill vd">{sv('unlock')}</span></dd>
  <dt>the wedge</dt><dd>{sv('wedge')}</dd>
  <dt>mechanic</dt><dd><span class="pill">{sv('mechanic')}</span>
      <span class="pill">{sv('model')}</span><span class="pill">{sv('loop')}</span>
      <span class="pill">{sv('moat')}</span></dd>
  <dt>not obvious</dt><dd>{esc(notes.get('why_not_obvious', ''))}
      <span class="fine">originality {esc(l1.get('originality'))};
      nearest shipped: {esc(l1.get('nearest_product') or 'none found')}</span></dd>
  <dt>build</dt><dd class="num">${esc(f"{l3.get('build_cost_usd', 0):,.0f}" if l3.get('build_cost_usd') else '?')}
      &middot; {esc(l3.get('weeks_to_v1'))} weeks &middot; {esc(l3.get('stack', ''))}</dd>
  <dt>economics</dt><dd><span class="pill {econ_pill}">margin {esc(l3.get('margin_ratio'))}</span>
      <span class="num fine">${esc(l3.get('price_month'))}/mo at
      {esc(round((l3.get('expected_conversion') or 0) * 100, 1))}% conversion,
      model cost ${esc(l3.get('inference_cost_user_month'))}/active user</span></dd>
  <dt>survived</dt><dd class="num">{esc(round((sc.get('survival') or 0) * 100))}% of attacks</dd>
  <dt>evidence</dt><dd class="fine">{" &middot; ".join(cites) if cites else "uncited"}</dd>
</dl>
<details><summary>Kill conditions and the build</summary>
<p class="fine" style="margin-top:9px"><b>This is wrong if:</b></p>
<ul class="tight">{kills}</ul>
{'<p class="fine" style="margin-top:9px"><b>Build path:</b></p><ul class="tight">' + miles + '</ul>' if miles else ''}
{'<p class="fine" style="margin-top:9px"><b>Riskiest assumption:</b> ' + esc(l3.get('riskiest_technical_assumption', '')) + '</p>' if l3.get('riskiest_technical_assumption') else ''}
{'<p class="fine"><b>Cheapest test:</b> ' + esc(l3.get('cheapest_way_to_test_that_assumption', '')) + '</p>' if l3.get('cheapest_way_to_test_that_assumption') else ''}
</details>
{attacks}
</article>"""


def _vp(verdict: str | None) -> str:
    return {"fatal": "bad", "wounded": "bad", "survived": "ok"}.get(verdict or "", "")


def _kill_log(killed: list[dict]) -> str:
    if not killed:
        return ""
    rows = "".join(
        f'<tr><td class="num">{esc(k["killed_at_gate"])}</td>'
        f'<td>{esc(k["title"])}</td>'
        f'<td class="fine">{esc(k["kill_reason"])}</td></tr>'
        for k in sorted(killed, key=lambda x: x["killed_at_gate"] or ""))
    return (f'<section><div class="shead"><div class="eyebrow">Kill log</div>'
            f'<h2>What died and where</h2><p class="col">The kill log is as much '
            f'of the output as the survivors. It is what makes the ranking '
            f'auditable rather than asserted.</p></div>'
            f'<div class="tscroll"><table><thead><tr><th>Gate</th><th>Idea</th>'
            f'<th>Reason</th></tr></thead><tbody>{rows}</tbody></table></div></section>')


def _evidence(sig_by_id: dict) -> str:
    kinds: dict[str, int] = {}
    for s in sig_by_id.values():
        kinds[s["kind"]] = kinds.get(s["kind"], 0) + 1
    pills = "".join(f'<span class="pill">{esc(k)} {v}</span>'
                    for k, v in sorted(kinds.items()))
    return (f'<section><div class="shead"><div class="eyebrow">Evidence base</div>'
            f'<h2>What the ideas were built from</h2></div><p>{pills}</p>'
            f'<p class="note" style="margin-top:14px">Every signal in the store '
            f'carries a live source URL. A claim with no citation is stripped at '
            f'gate L2, and an idea whose problem or enabling capability is left '
            f'uncited dies there.</p></section>')
