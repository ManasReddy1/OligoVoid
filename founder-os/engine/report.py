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

import diversity
import voidmap
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

    # ---- panel calibration ----
    parts.append(_panel_calibration(store, cycle_id))

    # ---- coverage ----
    parts.append(_coverage(store))

    # ---- diversity ----
    parts.append(_diversity(store, cycle_id))

    # ---- probes ----
    parts.append(_probes(store, {i["id"]: i for i in all_ideas}))

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

    rows = [
        ("for whom", sv("audience")),
        ("the problem", sv("pain")),
        ("why now", esc(notes.get("why_now", ""))),
        ("enabled by", f'<span class="pill vd">{sv("unlock")}</span>'),
        ("the wedge", sv("wedge")),
        ("mechanic", f'<span class="pill">{sv("mechanic")}</span>'
                     f'<span class="pill">{sv("model")}</span>'
                     f'<span class="pill">{sv("loop")}</span>'
                     f'<span class="pill">{sv("moat")}</span>'),
        ("not obvious", esc(notes.get("why_not_obvious", "")) +
         f'<div class="fine">originality {esc(l1.get("originality"))} &middot; '
         f'nearest shipped: {esc(l1.get("nearest_product") or "none found")}</div>'),
    ]

    # Stages that have not run yet are omitted rather than shown empty. A blank
    # margin reads as a margin of zero, which is a different claim.
    if l3.get("build_cost_usd") is not None:
        rows.append(("build",
                     f'<span class="num">${l3["build_cost_usd"]:,.0f} &middot; '
                     f'{esc(l3.get("weeks_to_v1"))} weeks</span> '
                     f'<div class="fine">{esc(l3.get("stack", ""))}</div>'))
        rows.append(("economics",
                     f'<span class="pill {econ_pill}">margin '
                     f'{esc(l3.get("margin_ratio"))}</span>'
                     f'<div class="fine num">${esc(l3.get("price_month"))}/mo at '
                     f'{esc(round((l3.get("expected_conversion") or 0) * 100, 1))}% '
                     f'conversion, model cost '
                     f'${esc(l3.get("inference_cost_user_month"))} per active user</div>'))
    if l4.get("survival") is not None:
        rows.append(("survived",
                     f'<span class="num">{round(l4["survival"] * 100)}% of attacks</span>'
                     + (f' <span class="pill bad">fatal: '
                        f'{esc(", ".join(l4.get("fatal_surfaces") or []))}</span>'
                        if l4.get("fatal_surfaces") else "")))
    rows.append(("evidence",
                 f'<span class="fine">{" &middot; ".join(cites) if cites else "uncited"}</span>'))

    kv = "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in rows if v)

    score_block = ""
    if sc.get("founder_score") is not None:
        score_block = (f'<div class="score">{esc(sc.get("founder_score"))}</div>'
                       f'<div class="heads"><span>novelty <b>{esc(sc.get("novelty"))}</b></span>'
                       f'<span>viability <b>{esc(sc.get("viability"))}</b></span></div>')

    extra = ""
    if l3.get("riskiest_technical_assumption"):
        extra += (f'<p class="fine" style="margin-top:9px"><b>Riskiest assumption:</b> '
                  f'{esc(l3["riskiest_technical_assumption"])}</p>')
    if l3.get("cheapest_way_to_test_that_assumption"):
        extra += (f'<p class="fine"><b>Cheapest test:</b> '
                  f'{esc(l3["cheapest_way_to_test_that_assumption"])}</p>')

    return f"""<article class="card{' top' if n <= 3 else ''}">
<div class="chead">
  <div><span class="rank">#{n} &middot; island {esc(r['island'])} &middot; {esc(r['operator'])}</span>
  <h3>{esc(g.get('title'))}</h3></div>
  <div style="text-align:right">{score_block}</div>
</div>
<dl class="kv">{kv}</dl>
<details><summary>Kill conditions and the build</summary>
<p class="fine" style="margin-top:9px"><b>This is wrong if:</b></p>
<ul class="tight">{kills}</ul>
{'<p class="fine" style="margin-top:9px"><b>Build path:</b></p><ul class="tight">' + miles + '</ul>' if miles else ''}
{extra}
</details>
{attacks}
</article>"""


def _vp(verdict: str | None) -> str:
    return {"fatal": "bad", "wounded": "bad", "survived": "ok"}.get(verdict or "", "")


FRESH_MONTHS = 24


def _panel_calibration(store: Store, cycle_id: int) -> str:
    """Is the red team discriminating, or just wounding everything?

    A panel that returns the same verdict for nearly every idea produces a
    survival multiplier with no spread, which silently removes one of the two
    factors in the composite score. That is worth showing next to the rankings
    rather than discovering later.
    """
    counts: dict[str, int] = {}
    by_surface: dict[str, dict[str, int]] = {}
    for r in store.ideas(cycle_id=cycle_id):
        for v in store.verdicts(r["id"]):
            if v["gate"] != "L4":
                continue
            for a in ((v.get("detail") or {}).get("detail", {}).get("attacks") or []):
                verdict = a.get("verdict", "?")
                surface = a.get("surface", "?")
                counts[verdict] = counts.get(verdict, 0) + 1
                by_surface.setdefault(surface, {})
                by_surface[surface][verdict] = by_surface[surface].get(verdict, 0) + 1
    total = sum(counts.values())
    if not total:
        return ""

    order = ["survived", "wounded", "fatal", "abstain"]
    rows = "".join(
        f'<tr><td class="m">{esc(surf)}</td>' +
        "".join(f'<td class="num">{esc(by_surface[surf].get(v, 0))}</td>' for v in order) +
        "</tr>"
        for surf in sorted(by_surface))
    head = "".join(f"<th>{v}</th>" for v in order)

    survived_share = counts.get("survived", 0) / total
    warn = ""
    if survived_share < 0.10:
        warn = (f'<p class="note" style="margin-top:12px">Only '
                f'<strong>{counts.get("survived", 0)} of {total}</strong> attacks '
                f'were answered outright. When almost every exchange lands on the '
                f'same verdict, the survival multiplier stops separating ideas and '
                f'one of the two factors in the composite quietly stops doing work. '
                f'Either consumer ideas really are this fragile, or the rubric '
                f'rewards wounding. The fix is the calibration set, not a softer '
                f'panel.</p>')

    return (f'<section><div class="shead"><div class="eyebrow">Panel calibration</div>'
            f'<h2>Is the red team discriminating?</h2>'
            f'<p class="col">{esc(total)} attacks across {esc(len(by_surface))} '
            f'surfaces. An abstention is not counted as a survival.</p></div>'
            f'<div class="tscroll"><table><thead><tr><th>Surface</th>{head}</tr>'
            f'</thead><tbody>{rows}</tbody></table></div>{warn}</section>')


def _coverage(store: Store) -> str:
    """How much of the enumerated space anyone has actually touched.

    The direct analogue of OligoVoid's position-by-modification coverage
    matrix: the interesting number is not what is occupied, it is what is not.
    """
    unlocks = []
    fresh = set()
    for sig in store.signals("UNLOCK"):
        p = sig.get("payload") or {}
        key = p.get("key") or esc(sig["title"])[:32]
        unlocks.append({"key": key, "title": sig["title"]})
        fresh.add(key)          # every loaded unlock crossed within 24 months

    products = store.products()
    audiences = sorted({p["audience"] for p in products if p.get("audience")})
    if not unlocks or not audiences:
        return ""

    vm = voidmap.VoidMap(unlocks, audiences, products, fresh)
    cov = vm.coverage()
    revivals = vm.revival_candidates()
    c = cov["counts"]

    rows = "".join(
        f'<tr><td>{esc(label)}</td><td class="num">{esc(c[k]):>6}</td>'
        f'<td class="num">{esc(round(100 * c[k] / max(1, cov["total_cells"]), 1))}%</td></tr>'
        for k, label in ((voidmap.OCCUPIED, "occupied by a shipped product"),
                         (voidmap.TOMBSTONED, "tombstoned, tried and died"),
                         (voidmap.FRONTIER, "void, and a recent unlock applies"),
                         (voidmap.VOID, "void, no fresh unlock")))

    return (f'<section><div class="shead"><div class="eyebrow">Coverage</div>'
            f'<h2>How much of the space anyone has touched</h2>'
            f'<p class="col">Cells are unlock x audience x mechanic, built from '
            f'{len(unlocks)} capability changes, {len(audiences)} audiences and '
            f'{len(vm.mechanics)} mechanics observed in the product corpus. The '
            f'interesting number is not what is occupied.</p></div>'
            f'<div class="tscroll"><table><thead><tr><th>Cell state</th>'
            f'<th>Cells</th><th>Share</th></tr></thead><tbody>{rows}</tbody>'
            f'</table></div>'
            f'<p class="fine" style="margin-top:12px">'
            f'<strong>{esc(round(100 * cov["void_fraction"], 1))}%</strong> of the '
            f'enumerated space is unoccupied. {esc(len(revivals))} tombstoned cells '
            f'pair with a capability change that may have dissolved their cause of '
            f'death, which is the region this system is built to search.</p>'
            f'<p class="note" style="margin-top:12px">Read the direction, not the '
            f'number. Audiences here are raw strings taken from the product '
            f'corpus rather than a normalised taxonomy, so the space is '
            f'over-counted and the void share is inflated. The equivalent figure '
            f'in this repository&rsquo;s siRNA work is meaningful because its axes '
            f'are a closed vocabulary. Giving audiences the same treatment is the '
            f'next real improvement to this section.</p>'
            f'</section>')


def _diversity(store: Store, cycle_id: int) -> str:
    d = diversity.report(store, cycle_id)
    g, sv = d["generated"], d["survivors"]
    if not g.get("n"):
        return ""
    sg, ss = d["spread_generated"], d["spread_survivors"]

    def row(label, a, b):
        return (f"<tr><td>{esc(label)}</td><td class=\"num\">{esc(a)}</td>"
                f"<td class=\"num\">{esc(b)}</td></tr>")

    isl = " ".join(f'<span class="pill">island {k}: {v}</span>'
                   for k, v in d["islands_surviving"].items())
    rows = (row("candidates", g.get("n"), sv.get("n")) +
            row("unique audience x mechanic x unlock cells",
                g.get("unique_combinations"), sv.get("unique_combinations")) +
            row("distinct cells per candidate",
                g.get("combination_ratio"), sv.get("combination_ratio")) +
            row("distinct audiences", g.get("unique_audiences"), sv.get("unique_audiences")) +
            row("distinct mechanics", g.get("unique_mechanics"), sv.get("unique_mechanics")) +
            row("mean pairwise distance",
                sg.get("mean_pairwise_distance"), ss.get("mean_pairwise_distance")) +
            row("structural disorder",
                sg.get("structural_disorder"), ss.get("structural_disorder")))

    crowded = (f'Most crowded cell: <code>{esc(sv.get("most_crowded_cell"))}</code> '
               f'with {esc(sv.get("most_crowded_count"))} survivors.'
               if sv.get("most_crowded_count", 0) > 1 else
               "No cell holds more than one survivor.")

    return (f'<section><div class="shead"><div class="eyebrow">Diversity monitor</div>'
            f'<h2>Did the search collapse?</h2><p class="col">Optimising against any '
            f'scorer collapses diversity, and collapsed diversity destroys the point '
            f'of a search. These numbers are the alarm. A distinct-cells-per-candidate '
            f'ratio falling toward zero means the gates are selecting one idea in '
            f'many costumes.</p></div>'
            f'<div class="tscroll"><table><thead><tr><th>Measure</th>'
            f'<th>Generated</th><th>Survivors</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>'
            f'<p class="fine" style="margin-top:12px">{crowded} '
            f'Survivors by island thesis: {isl}</p></section>')


def _probes(store: Store, ideas_by_id: dict) -> str:
    probes = store.probes()
    if not probes:
        return ""
    cards = []
    for p in probes:
        d = p.get("result") or {}
        idea = ideas_by_id.get(p["idea_id"], {})
        steps = "".join(f"<li>{esc(x)}</li>" for x in (d.get("exactly_what_to_do") or []))
        cards.append(f"""<article class="card">
<div class="chead"><div>
  <span class="rank">{esc(p['kind'])} &middot; {esc(d.get('days', '?'))} days</span>
  <h3>{esc(idea.get('title', 'idea ' + str(p['idea_id'])))}</h3></div>
  <div class="score">${esc(round(p['budget_usd']))}</div></div>
<dl class="kv">
  <dt>testing</dt><dd>{esc(p['hypothesis'])}</dd>
  <dt>kills it if</dt><dd><span class="pill bad">{esc(p['falsifier'])}</span></dd>
  <dt>blind spot</dt><dd class="fine">{esc(d.get('what_it_cannot_tell_you', ''))}</dd>
</dl>
{'<details><summary>What to actually do</summary><ul class="tight" style="margin-top:9px">' + steps + '</ul></details>' if steps else ''}
</article>""")
    total = sum(p["budget_usd"] for p in probes)
    return (f'<section><div class="shead"><div class="eyebrow">Probe queue</div>'
            f'<h2>The cheapest way to find out</h2><p class="col">Everything above '
            f'this point is a proxy. These are the only tests that touch ground '
            f'truth, and nothing runs without you approving the spend. Total for '
            f'the queue: <strong>${total:,.0f}</strong>.</p></div>'
            f'{"".join(cards)}</section>')


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
