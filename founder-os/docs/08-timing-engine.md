# The timing engine

The one component every product in this space needs, derived from the pain
evidence rather than from a product decision. Written before choosing what to
build, because whatever gets built fails without it.

---

## What the evidence says the problem is

Across 30 cited complaints, the failure is not memory. It is timing.

> "I was reminded at a moment when I could not act, so I dismissed it, and
> dismissing became the habit."

Three of the clearest instances:

- A person wants reminding **upstairs, right before bed**, not downstairs at the
  computer where the reminder is useless.
- A person is reminded **after already doing the task** and says he will
  eventually start ignoring the reminders.
- The author of a call-your-mother tool abandoned calendar events because it
  notified him **on days he had already called**.

And the same failure seen from the other side, when a goal is enforced at a
clock edge instead of a window of capability: a language lesson played at 1am
with half-open eyes purely to hold a streak; a meditation logged at 11:56pm and
actually performed at 2am. When the clock finally wins, people abandon **the
goal**, not the tool. One person lost a streak at 12:01am and never opened the
app again.

That last detail is the important one. A badly timed system does not merely
fail to help. It destroys the thing it was hired to protect.

---

## Two rules that follow

### 1. Trigger on a window of capability, never on a clock edge

The question is never what time it is. It is whether this person can act in the
next few minutes. A window is a predicate over context, not a timestamp.

Signals that are actually available under the platform rules:

| Signal | What it tells you | Availability |
|---|---|---|
| Motion and activity state | walking, driving, stationary | both platforms |
| Geofence arrival and departure | home, work, gym, the parent's house | both, no continuous location needed |
| Calendar free or busy | whether they are in something right now | both, with permission |
| Focus state | the user's own declaration of what they are doing | iOS, app can react to Focus changes |
| Workout or sleep ended | a natural seam in the day, and a legitimate self-wake trigger | HealthKit background delivery |
| Charging, Wi-Fi at home, screen unlock after a gap | settled rather than in motion | both |
| Notification activity | what they are already doing | Android only |

None of this requires the app to run continuously. Every one of these is a
trigger the platform will wake you for, which matters because ambient
background reasoning is not permitted on either platform.

### 2. A dismissal must cost the system, not the user

If dismissing is free, the product is training the user to dismiss. Every
product in this graveyard trained its users to dismiss.

The mechanism that fixes it is a hard **interruption budget**: a small fixed
number of prompts per day, spent by the system. Two consequences follow
automatically.

- The system must **choose**. With one prompt to spend, surfacing the third-best
  thing is a real loss, so selection pressure exists without any extra
  machinery.
- A dismissal is **expensive**, because the budget is gone. That makes each
  dismissal worth learning from rather than absorbing silently.

Every dismissal is a labelled negative example for "this context was
actionable". Every action taken without a prompt is a positive example for the
context it happened in. The window model is trained on the user's own behaviour,
which is also the record a competitor cannot copy.

---

## The shape of the component

```
commitments          window model              budget
(typed rows)   x   (is now actionable?)   x   (1-3/day)
       │                    │                    │
       └────────────► score each ◄───────────────┘
                            │
                    surface AT MOST ONE
                            │
                   prepared, one tap to confirm
                            │
              outcome ──► both models update
```

**Commitments** are typed rows, not chat history: who or what, a due window
rather than a due time, the trigger condition, and the single action that
would discharge it.

**The window model** starts as a hand-written prior (do not interrupt while
driving, do not fire during a calendar event, prefer the seam after a workout)
and is then corrected by the user's own dismissals and unprompted actions. It
stays a small model precisely because on-device context is about 4K tokens
locally and 32K on Apple's free tier, so it cannot be a prompt over a life
history. Compactness is a requirement, not an aesthetic.

**The budget** is the selection pressure. Default one interruption a day, raised
only by the user.

---

## Why a general assistant does not simply do this

A first-party assistant can fire a reminder. It cannot hold an interruption
budget, because it does not know what else it will need to say to you today, and
it cannot afford to be wrong about your day in a way that a product you chose
for exactly this can.

It also cannot learn from your dismissals the way this does, because a
dismissal of a system notification is not a signal about a commitment you made.
The learning here only works because the commitment was declared first, which
is the same act that creates the record.

---

## How this gets tested cheaply

The whole component is falsifiable before any of it is built:

- **Wizard of Oz for two weeks.** A person watches five volunteers' calendars
  and locations, sends one message a day by hand at the moment they judge
  actionable, and records whether it was acted on. If a human with full context
  cannot beat a fixed 9am reminder, no model will.
- **The falsifier**: fewer than half of the hand-timed prompts acted on within
  an hour, against a fixed-time control.

That is the probe this component deserves, and it costs nothing but attention.
