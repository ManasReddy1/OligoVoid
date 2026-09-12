# The memory model

The third component that every product in this space needs, and the only one
that can become a moat. Written from the constraints rather than from a product
choice.

---

## Why this is the moat and nothing else is

Models are a commodity. Any feature in this category is copyable in a quarter,
and the graveyard proves it: Sunrise, Timeful, Tempo, Woven and Inbox were not
outcompeted, they were **absorbed**, because value in calendar, email and
contacts accrues to whoever owns the account.

The one thing that does not transfer to an incumbent is a record of one person
that was **built by that person's own behaviour**, that the incumbent never
observed, and that would hurt to abandon. Everything else in the design exists
to produce that record as a side effect of being useful.

There is also a platform fact that makes this a real opportunity rather than a
consolation: **no first-party persistent personal-memory API exists for third
parties on either platform.** Nobody is going to hand you this, and nobody is
going to take it from you either.

---

## The constraint that shapes everything

On-device context is roughly **4K tokens locally** and **32K on Apple's Private
Cloud Compute**. A life history does not fit in a prompt and never will.

That rules out the obvious design, which is to keep a transcript and let the
model read it. It forces the design that is better anyway: a **typed record
with a small rolling state**, where the model reasons over a compact summary and
retrieves detail only when it needs it.

Compactness here is not an optimisation. It is the thing that keeps the product
working at year three, when a transcript-based competitor has become unusably
slow and expensive.

---

## Three layers

### 1. The commitment ledger — typed rows, not chat

Every commitment is a row, not a sentence in a log:

| Field | Why it is separate |
|---|---|
| `subject` | the person or the goal it concerns |
| `intent` | what the user said they would do, in their own words |
| `window` | a due **window**, never a due time, because clock edges produce clock-satisfying behaviour |
| `trigger` | the context that makes it actionable |
| `discharge` | the single action that closes it |
| `declared_at` | when the user committed, which is what makes it theirs |
| `history` | prompted, dismissed, acted, at what and where |

The row is the unit because it is queryable, countable and auditable. A
transcript is none of those, and the difference shows up the first time the
product has to answer "what did I say I would do about my father".

### 2. The rolling state — one page, always current

A single compact summary, kept under a couple of thousand tokens, holding: who
matters right now, what is open, what has been slipping, what the person has
been consistent about lately, and what they have asked not to be pushed on.

It is regenerated on a schedule from the ledger, not appended to. Append-only
summaries grow without bound, which is the same failure as the transcript one
step removed.

This page is what goes into the model's context. Everything else is retrieved.

### 3. The behaviour model — the part nobody can copy

Two small learned things, trained only on this person:

- **When they can act.** Corrected by every dismissal and every unprompted
  action, as described in the timing engine.
- **What they actually do versus what they say.** The gap between declared
  intent and discharged commitment, per subject. This is the honest signal
  underneath the whole product, and it can only be earned over months.

An incumbent shipping the same features on day one still has neither of these.

---

## What to store and what to refuse to store

Refusing is part of the design, not a compliance afterthought.

**Store**: what the user declared, what the product prompted, what happened
next. All of it on-device by default, exportable, deletable per subject.

**Do not store**: message content, call content, or anything the user did not
choose to tell the product. Not because it is unavailable, though on iOS it
largely is, but because a product whose premise is "hold me to what I said"
collapses the moment its user wonders what else it heard.

That refusal is also the reason the free on-device tier and Private Cloud
Compute matter beyond cost: nothing needs to leave the phone, so the promise is
structural rather than a policy page. The 2026 App Review guideline requiring
explicit consent before sending personal data to third-party AI providers is a
consent prompt a competitor has to show and this design does not.

---

## Portability, which is the uncomfortable part

A record that hurts to abandon is a moat. A record the user cannot take with
them is a hostage, and the graveyard is full of products whose users lost
everything when they shut down: Moxie bricked with no refunds, Jibo delivered a
farewell message, Car Thing was remotely disabled.

The resolution is to make export complete and boring: the ledger and the state
page, in a readable format, on demand. The moat survives it. Nobody rebuilds
two years of behavioural correction from a JSON file, and offering it is what
makes the record feel like the user's rather than the company's.

---

## How this gets tested before it is built

The memory model is falsifiable on paper, which is unusual and worth using:

- Take four weeks of one real person's commitments, written by hand.
- Generate the rolling state page from them.
- Ask whether a stranger reading only that page could pick the right thing to
  surface on a given Tuesday afternoon.
- **The falsifier**: if the page needs more than roughly 2,000 tokens to be
  useful at four weeks, it will not survive year one, and the design is wrong
  before any code exists.
