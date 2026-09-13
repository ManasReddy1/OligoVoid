# Second Voice

A mentor app that answers the sentence in your head.

Not "a quote a day". The corpus is indexed by **the belief each line refutes**,
so when you are about to not do something, you name the reason you are giving
yourself and it hands you the person who already argued against exactly that —
plus a smaller version of the task you can still do.

```
you skip a block  →  "what's the sentence in your head?"  →  the refutation  →  the smaller move  →  logged
```

After a fortnight the Log tab shows the two or three sentences responsible for
most of what you did not do. That record is the point; the quotes are the
delivery mechanism.

## Run it

No build step, no server, no account, no key. State lives in your browser.

```bash
cd mentor
python3 -m http.server 8080     # file:// works too, but the service worker needs http
```

Single self-contained file, for putting on a phone or emailing to yourself:

```bash
python3 build_single.py         # → dist/mentor.html
```

## Tests

```bash
node test_match.js   # matcher accuracy + corpus hygiene
node smoke.js        # drives the real UI in Chromium end to end
```

## What works, and the part that does not

`test_match.js` reports two numbers. The tuned set scores 22/22 because the
phrasings were written against it. **The held-out set — written afterwards,
deliberately worded differently — scores 2/15 top-1 and 7/15 top-3.**

That is the honest number, and it is why typing does not assert an answer. People
type a *situation* ("I've had this email open in a tab since Monday"), not a
belief ("I keep putting this off"), and no amount of lexical matching crosses
that gap. So typing filters a browsable list of thirty beliefs and you pick. The
choice stays yours, it works offline, and it is right more often than a confident
wrong guess.

Free-text → belief needs a language model. On a phone that is free and private
(on-device or Apple's Private Cloud Compute tier); in a browser it would mean
shipping an API key to the client, which is why it is not here.

## What a web app cannot do

It cannot wake you up. Notifications from a page only fire while the page is
alive in the background, a phone will suspend it, and nothing on the web gets
past silent mode or a Focus. The reminder layer here is a working demonstration
of the interruption budget, not a dependable alarm.

The alarm layer needs a native app. On iOS that only became possible with
**AlarmKit in iOS 26** (June 2025), which lets a third-party app raise a
full-screen alert through silent mode and Focus with its own stop and snooze
buttons — which is the exact surface this product wants, because the moment the
thumb reaches for *stop* is the moment worth interrupting.

## Files

| | |
|---|---|
| `corpus.json` | 30 entries: belief, phrasings, quote, source, honest attribution label, refutation, smaller move |
| `match.js` | IDF-weighted cosine with a light stemmer; runs in node and the browser so it can be tested headless |
| `app.js` | schedule, the stuck flow, the log, the interruption budget |
| `index.html` `styles.css` `sw.js` `manifest.webmanifest` | the shell, offline-capable |
| `build_single.py` | inlines everything into `dist/mentor.html` |

## On the quotes

Roughly a fifth of famous quotations are attached to the wrong person, and quote
apps are the main reason. Every entry carries a label: **verified**,
**commonly attributed**, or **check the source** — the last one naming who
actually said it. "We are what we repeatedly do" is Will Durant, not Aristotle.
"Comparison is the thief of joy" has never been found in Roosevelt. The
labelling is a feature, not a disclaimer.
