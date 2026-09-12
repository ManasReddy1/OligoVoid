# What a phone assistant is actually allowed to be, in 2026

Evidence layer for any product that acts on someone's phone. Harvested from
platform documentation, store policy and agent benchmarks, with 29 cited rules
in `engine/data/platform_limits.json`.

This is written before choosing a product, because these rules decide which
products are possible and no amount of design gets around them.

---

## The decisive answer

**A third-party consumer app on a stock phone cannot perform multi-step actions
across other apps on the user's behalf.** Not on iOS, not on Android, and not by
an accident of missing APIs. By explicit rule, on both platforms.

### iOS

- There is **no public API for one app to invoke another app's App Intent**.
  App Intents expose *your* app to the system. Multi-app composition is reserved
  for Siri.
- **Guideline 2.5.11(i)**: apps "should only sign up for intents they can handle
  without the support of an additional app".
- **Guideline 2.5.2**: no code that introduces or changes features of other apps.
- **Messages is closed**: no programmatic send, no read access, and — the fact
  that reshapes the whole product — **no contact-recency signal**. An iOS app
  cannot see who you last spoke to.
- **Screen Time** data arrives as opaque tokens inside a network-less extension,
  so it cannot be reasoned over.

### Android

- Google Play's accessibility policy bans "use of the Accessibility API that
  enables an app to autonomously initiate, plan, and execute actions or
  decisions". It permits only "deterministic, rule-based automation, where
  behavior follows a static, human-defined script", and names **assistants and
  automation tools as ineligible categories**.
- Android 17's Advanced Protection Mode auto-revokes the permission from
  anything not tagged as an accessibility tool, since June 2026.
- `SEND_SMS` and `CALL_PHONE` are reserved for the **default handler** app.
- The sanctioned cross-app path, **AppFunctions**, is an experimental preview
  gated to an early access programme whose members are large marketplaces.

### And the models are not ready either

| Benchmark | Best result |
|---|---|
| OSWorld 2.0, long-horizon desktop tasks | **20.6%** completed |
| MobileWorld, realistic mobile tasks | **51.7%**, and it hallucinates rather than asking on **22.4%** of ambiguous tasks |
| AndroidWorld | saturated above 90%, which is why demos look good |

The gap between AndroidWorld and MobileWorld is the gap between a demo and a
product. Policy and reliability point the same way, so a product betting on
either changing is betting twice.

---

## What is open

The shape the rules leave is narrow and specific:

> **Sense broadly. Reason locally. Act narrowly, through one tap.**

### Sensing: real, and asymmetric between platforms

| Signal | iOS | Android |
|---|---|---|
| Message and app activity | closed | **NotificationListenerService** gives genuine ambient awareness |
| Health and workouts | **HealthKit background delivery**, one of the few reliable self-wake triggers | available |
| Calendar, contacts, location, motion, focus state | available with permission | available with permission |
| Who you last contacted | **not available** | inferable from notifications |

The iOS contact-recency gap is the single most consequential line in this
document. It means a relationship product on iOS cannot passively notice that
you have fallen out of touch. The user has to **declare** the people who matter.

That sounds like a limitation and is closer to a feature: declaring who matters
is an act of commitment, and the declaration is the first row of the personal
record that later becomes the only thing a competitor cannot copy.

### Reasoning: free, and tighter than expected

- **Apple Private Cloud Compute at zero cloud API cost** for Small Business
  Program members under 2M lifetime downloads.
- On-device Foundation Models in 2026 have vision, roughly **4K context locally**
  and **32K on Private Cloud**.
- **No first-party persistent personal-memory API exists** for third parties on
  either platform. You build the memory yourself, and you own it.

4K of local context is the design constraint that matters. You cannot stuff a
person's history into a prompt. You need a **compact, typed state** that stays
small as the record grows, which is a discipline rather than a handicap.

### Acting: one tap, and only your own surfaces

What you can do is prepare an action and hand it to the user:

- a message composer, prefilled, where **the user taps Send**
- a call the user confirms
- a calendar event, a health log, a workout start, your own app's intents

What you own outright as a proactive surface:

- **Live Activities**, startable remotely by push, now policed by guideline
  4.5.3 against ambient non-event use
- Android's **Live Updates**, which are largely unclaimed

### The strategic inversion worth noting

Apps that publish App Intents become **components in Siri's own compositions**.
You cannot build the agent that orchestrates other apps. You can be the app the
OS agent calls. That is a different product from the one people imagine, and it
is the one the platform is actively recruiting for.

---

## What this rules out, before any design work

| Tempting | Why it cannot ship |
|---|---|
| "It does things across your apps for you" | No API on iOS, policy ban on Android, 20.6% reliability |
| "It reads your texts and notices you've gone quiet with someone" | iOS has no contact-recency signal at all |
| "It texts people for you" | Neither platform permits a send without the user's tap |
| "It watches your screen time and coaches you" | Screen Time tokens are opaque and network-less |
| "It remembers everything, using the OS memory layer" | No such API exists for third parties |
| "It runs continuously in the background, thinking" | Background execution is trigger-based, not ambient |

Every one of these appears in the pitch of a product that died. The rules were
the same when they pitched it.
