# The mentor app: what already exists, and the one part that does not

Run against the same question the engine asks of everything: does this need to
be built, and if so, which part.

---

## The honest answer first: most of it is built

| The part you described | Already shipping |
|---|---|
| Alarm that gives you a motivational quote | **Quotes Alarm**, **Rise – Motivational Alarm**, **Inspire Alarm Clock**, **MOTIVE**, **Motivational Alarm Clock** |
| Alarm you must beat with effort or a partner | **Rise – Read To Wake** (read your words aloud to dismiss), **AccAlarm**, **UpCast** (your friend is told when you snooze) |
| Asks your schedule, plans your day, reminds you | **Motion** (auto-schedules), **Sunsama** (guided daily ritual + evening reflection), **Structured**, **Tiimo**, **Reclaim** |
| Describe your situation, get a philosopher's answer | **Seneca Chat** — Stoic principle applied to what you typed |

So: a discipline coach that wakes you and reminds you is a saturated category,
and a quote-at-the-alarm app has been built at least six times. Building that
again is not a small bet with high ROI. It is the most crowded shelf in the
store.

**If the goal is the workflow rather than the product**, the existing stack is
Sunsama or Structured for the day, the phone's own alarm for the morning, and a
chat assistant when stuck. That combination costs about $20/month and needs no
building.

---

## The part that is not built

The story in the original request is the evidence, and it is worth reading
precisely. A quote about stories already existing helped — not because it was
inspiring, but because it **refuted a specific false belief** being held at that
moment: *my idea already exists, therefore it is worthless.*

That is not a quote app. That is retrieval **indexed by the belief a line
refutes**.

Every existing product indexes by theme — motivation, discipline, creativity —
and delivers on a schedule. None index by the sentence in your head, and the
sentence is the only thing that decides whether a line lands. The same Marcus
Aurelius passage is useless at 3pm and decisive at 6:30am with a thumb on the
stop button.

Three consequences follow, and they are the whole design:

1. **The trigger is the moment of resistance, not the clock.** The product's one
   job is to be present when you are about to not do something.
2. **A refutation ships with a smaller move.** Doc 08's red team killed the
   information-only version: *the barrier is avoidance, not information*. A
   well-timed quote aimed at an avoided task removes the last excuse and still
   gets dismissed. Every entry therefore carries a downgraded action that still
   counts.
3. **The excuse log is the asset.** After two weeks the user can see the two or
   three sentences responsible for most of what they did not do. Nobody else has
   that record, it gains value per entry, and cancelling loses it — the same
   shape that won cycle 2.

---

## What was actually built

`mentor/` in this repository. Working, offline, no key, no account.
30 corpus entries, a schedule with an interruption budget, the stuck flow, the
log. `node test_match.js` and `node smoke.js` both pass; the smoke test drives
the real UI in Chromium.

### The finding that changed the design

Free-text matching was tested on a held-out set written *after* the corpus
phrasings and deliberately worded differently:

| set | top-1 | top-3 |
|---|---|---|
| tuned (phrasings written against it) | 22/22 | 22/22 |
| **held-out** | **2/15** | **7/15** |

People type a situation — "I've had this email open in a tab since Monday" —
not the belief under it. Lexical matching cannot cross that gap and the tuned
number is self-congratulation.

So typing **filters** a browsable list of thirty beliefs instead of asserting an
answer. It works offline, it is honest, and it is right more often than a
confident wrong guess. Free text → belief is a language-model job; on a phone
that is free and private via on-device models or Apple's Private Cloud Compute
tier, and in a browser it would mean shipping a key to the client, so it is not
in the web build.

---

## Platform reality

Per doc 07, a web page cannot wake you. Notifications fire only while the page
survives in the background, the OS suspends it, and nothing on the web passes
silent mode or a Focus. The reminder layer in `mentor/` demonstrates the
interruption budget; it is not a dependable alarm.

The alarm needs a native app, and the relevant capability is recent:
**AlarmKit, iOS 26, June 2025.** A third-party app can now raise a full-screen
alert through silent mode and Focus with its own stop and snooze buttons,
reaching the Lock Screen, Dynamic Island and Watch — previously Clock-only.

That matters more than it sounds. The product's best moment is the thumb
reaching for *stop*, and until iOS 26 no third party could own that screen. It
is a dated unlock in the sense the engine means: a capability that changed, with
a window before the shelf fills.

---

## Cost, and the probe that comes first

| | |
|---|---|
| Web version | built, in `mentor/`, cost nothing |
| Native iOS with AlarmKit | roughly 4–6 weeks, $3,000–6,000 at contract rates |
| Corpus verification pass | 2–3 days; every attribution checked against a primary source |
| Marginal model cost | ~zero on-device / Private Cloud Compute |

**Do not build the native app yet.** The falsifiable claim is not "can this be
built" — it obviously can. It is:

> Does a refutation aimed at the specific belief change behaviour more than a
> generic motivational quote?

Test it for free, over two weeks, with the web version already sitting in
`mentor/`: use it yourself and give it to five people, log every stuck moment,
and count how often the smaller move actually got done.

**The falsifier:** if the smaller move is done less than half the time, the
mechanism is not working and the alarm layer would only make a non-working
mechanism louder. The refutation category is then dead and $5,000 was not spent
proving it.

The honest base rate remains the one from doc 05: 4.6% of new subscription apps
reach $10,000/month within two years. This is cheaper than most and, unlike the
sixth motivational alarm clock, it is at least not a copy.

---

## Sources

- AlarmKit / iOS 26 third-party alarms — https://www.macrumors.com/2025/06/11/ios-26-third-party-alarm-apps/
- Rise – Read To Wake Alarm — https://play.google.com/store/apps/details?id=com.jhoox.riseapp
- UpCast: Social Alarm Clock — https://apps.apple.com/us/app/upcast-social-alarm-clock/id6761076455
- AccAlarm: Accountability Alarm — https://play.google.com/store/apps/details?id=com.shivion.accalarm
- Quotes Alarm — https://quotesalarm.com/
- Seneca Chat (situation → Stoic principle) — https://senecachat.com/app/ai-philosophy-chat
- Daily planner landscape (Motion, Sunsama, Structured, Tiimo, Reclaim) — https://efficient.app/best/daily-planner
