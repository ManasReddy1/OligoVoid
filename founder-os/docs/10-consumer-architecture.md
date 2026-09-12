# The architecture that survived

Cycle 2 pointed the engine at your question: a phone-resident assistant that
keeps you on top of people, commitments, health and goals. Seven opposing
theses, 28 candidates, six gates, 85 recorded attacks.

**Twenty of twenty-eight died. The winner is not an assistant.**

---

## What the ranking said

| Score | Idea | Survived attacks | Build |
|---|---|---|---|
| **59.1** | Shared handoff record for court-supervised custody | **80%** | $4,900, 11w |
| 39.7 | Expense ledger for siblings paying a parent's costs | 60% | $5,400, 11w |
| 34.7 | Scan-in weekly meal binder | 50% | $1,700, 6w |
| 33.8 | Power-of-attorney document ledger | 50% | $3,600, 9w |
| 33.5 | Who-gave-which-dose record for sibling carers | 50% | $3,300, 9w |

The gap between first and second is the whole story. One idea survived four
fifths of everything thrown at it. Nothing else cleared 60%.

And every survivor in that list is the same object: **a shared record of what
happened, kept by people who are already keeping it by hand.**

Not one is a reminder app. Not one is a coach.

---

## Why the Jarvis shape died

Your description had four jobs in it: people, reminders, health, motivation. All
four lost, for three separate reasons.

**The execution half is illegal.** A third-party app cannot drive other apps on
either platform. No public API on iOS, and Google Play bans using the
accessibility API to autonomously initiate, plan or execute actions, naming
assistants as an ineligible category. The best agent completes 20.6% of
long-horizon tasks anyway. Buildability killed the three most execution-heavy
candidates, including one that died on both schedule and margin because it
needed App Review to accept an app-initiated call.

**The briefing half was already run at planetary scale and shut down.** Google
Assistant Snapshot had the best data, the best models and default placement on
every Android phone. Google killed it because nobody engaged. The daily-briefing
candidate here died on demand, incumbent response and retention simultaneously.

**The reminder half trains its user to ignore it.** The retention attacker found
one signature under every fatal verdict: a prompt at a clock edge, about a task
that cannot be finished in one tap, with no accumulating state to lose at
renewal.

---

## The shape that survived, stated generally

> **A shared, timestamped record of something consequential, kept by people who
> already keep it by hand, where an outside force makes the keeping mandatory.**

Five properties, and the winner has all five:

| Property | Why it survives the gate that kills everything else |
|---|---|
| **Someone outside insists** | The trigger is not a clock edge you invented. A court order, a lookback audit, a handover between two carers. Retention stops depending on motivation. |
| **They already do it by hand** | Demand is observed, not stated. The demand attacker killed every idea whose evidence was people *saying* they felt guilty, and spared the ones where someone is already typing this into Notes. |
| **The record gains value per entry** | At renewal the question becomes *do I want my record*, not *did I use this enough*. That is the only version of the question you win at month one. |
| **More than one person touches it** | The second person is the distribution loop and the reason it cannot be abandoned unilaterally. |
| **No incumbent wants it** | Apple and Google will not build a custody evidence log. It is small, it is legally fraught, and it requires taking a side. |

---

## The architecture

Three components, each documented separately, each forced by evidence rather
than chosen.

```
  SENSE ─────────► TIMING ─────────► ACT
  what the phone   window of         one tap,
  will tell you    capability,       your own surface
       │           not clock edge        │
       └──────────────┬──────────────────┘
                      ▼
                   MEMORY
           typed ledger + rolling state
         the only thing that cannot be copied
```

**Sense** (`07-phone-agent-substrate.md`). Geofences, calendar free/busy,
motion, Focus state, HealthKit background delivery. All triggers the OS wakes
you for, because ambient background reasoning is permitted on neither platform.

**Timing** (`08-timing-engine.md`). Fire on a window of capability. Hold a hard
interruption budget of one or two prompts a day, so the system must choose and a
dismissal costs it something. Note the limit the red team found: timing fixes
being prompted when you cannot act, and does nothing for avoidance.

**Memory** (`09-memory-model.md`). A typed ledger, not a transcript, because
on-device context is roughly 4K tokens. A rolling state page under 2K tokens.
The moat must exist by **day 30**, not year two, because that is when churn is
decided.

**Act.** Prepare, never perform. A prefilled composer the user sends. A
confirmed call. A Live Activity, which is the one proactive surface you own
outright.

---

## The honest business case

At $4,900 and eleven weeks the winner is inside your budget with room to spare.

| | |
|---|---|
| Build | $4,900, 11 weeks, one person |
| Marginal model cost | near zero, on-device and Apple's free tier under 2M downloads |
| Price | a category where people already pay for court-mandated tooling |
| Distribution | the second parent and the practitioner who told them to keep records |

The realistic target is not a unicorn. **Only 4.6% of new subscription apps
reach $10,000 a month within two years.** This shape aims at that 4.6% by
picking a population that is already paying someone for a worse version.

---

## What to do next, cheaply

The probe this deserves costs nothing:

1. Post in the forum where these people already gather and ask what they
   currently use to keep the record.
2. **The falsifier**: fewer than five unprompted replies describing a manual
   system within 72 hours.

If people are not already keeping the record by hand, the whole shape collapses,
and you will know inside three days for zero dollars.

---

## The uncomfortable conclusion

You asked for a Jarvis. The machinery says the Jarvis is the part that is
blocked, already tried at scale, or self-defeating, and that the valuable thing
hiding inside your description is much smaller and much duller: **be the record
two people need to agree on.**

Nothing here is calibrated against real outcomes. Published benchmarks on this
class of prediction top out near a 4.7x lift over a sub-1% base rate. Treat the
ranking as a filter that removed twenty ideas for stated reasons, not as a
verdict on the one that is left.
