# Seed evidence — the day-one signal load

The evidence layer's first harvest, done by hand so the architecture can be reviewed
against real inputs rather than hypothetical ones. Every row is what a `Signal`
would look like after normalisation. Nothing here has been through the pipeline —
these are inputs, not outputs.

Dates are as of September 2026. Confidence flags matter: several widely-repeated
figures could not be traced to a primary source and are marked.

---

## The market shape, in one paragraph

Consumer apps in 2026 are a **revenue-rich, download-poor, retention-brutal**
market. Spending grew ~21% while downloads fell 2.7% for the fifth consecutive year
from the 2020 peak. **Non-game app spend passed games for the first time in
history** and is growing 3-5x faster. Institutional capital has largely left
consumer — roughly 5% of the most recent YC batch — which means less funded
competition and no realistic venture path at this budget. The realistic target is
not a unicorn; it is the **4.6%** of subscription apps that reach $10k monthly
revenue within two years.

---

## UNLOCK signals — what became possible

| Capability | Old cost | New cost | Crossed | Source |
|---|---|---|---|---|
| Frontier-class text inference | $30/M in, $60/M out (GPT-4, Mar 2023) | $0.10/M in, $0.40/M out (Gemini 3.1 Flash, Apr 2026) | 2026 | [a16z LLMflation](https://a16z.com/llmflation-llm-inference-cost/) |
| Cost to reach a fixed capability | — | falls **9x-900x per year**, ~200x for post-2024 models | ongoing | Epoch AI |
| Long context | RAG pipeline plus vector DB | 1M-token context, **flat price at any length**, cached input at $0.075/M (90% off) | 2026 | [Gemini pricing](https://benchlm.ai/google/api-pricing) |
| Real-time voice | uneconomic | **$0.005-$0.018/min** (Gemini Live) up to **$0.091/min** (flagship speech-to-speech) | 2026 | [Inworld voice cost](https://inworld.ai/resources/voice-agent-cost-per-minute-2026) |
| Video generation | product-priced | **$0.03/s** (Veo 3.1 Lite) — a 5-second clip is $0.15-$0.25 | 2026 | [pricing guide](https://fluxnote.io/blog/ai-video-generation-pricing-guide-2026) |
| **On-device and free cloud inference** | per-token cloud billing | **$0 cloud API cost** for Apple Foundation Models on Private Cloud Compute, for Small Business Program members under 2M lifetime downloads | Jun 2026 | [Apple Newsroom](https://www.apple.com/newsroom/2026/06/apple-aids-app-development-with-new-intelligence-frameworks-and-advanced-tools/) |
| On-device LLMs, full scale | not possible | Apple **Core AI** framework deploys full-scale LLMs locally; on-device model gained vision; a `Language Model` protocol swaps providers behind one interface | Jun 2026 | [WWDC26 session 241](https://developer.apple.com/videos/play/wwdc2026/241/) |
| On-device generative APIs, Android | not available | ML Kit **GenAI** on Gemini Nano via AICore — prompt, summarise, proofread, rewrite, image description, speech recognition. Free, offline, hardware-accelerated | 2026 | [Android docs](https://developer.android.com/ai/gemini-nano) |
| Age and identity verification | vendor contract | OS-level calls: Apple **Declared Age Range API**, Google **Play Age Signals API** | 2026 | [developer guide](https://www.bakerdatacounsel.com/blogs/an-app-developers-guide-to-app-store-age-assurance-laws/) |
| Smart glasses as a platform | closed | **Meta Ray-Ban Display opened to third-party developers 14 May 2026**, with an official plain HTML/CSS/JS path plus a mobile SDK and Neural Band gestures | May 2026 | [Meta developers](https://developers.meta.com/blog/build-for-display-glasses/) |

**The one that matters most at this budget:** Apple's free Private Cloud Compute
tier inverts the entire margin problem below. A solo founder can ship an AI consumer
app on iOS with **zero marginal inference cost** up to 2M downloads.

## SHIFT signals — platform and regulatory changes

| Change | Effective | Why it opens space |
|---|---|---|
| **US external payments at 0% Apple commission** | in force since May 2025; cert granted 30 Jun 2026 on the contempt question, merits ruling likely 2027 | A US app routing checkout to the web keeps ~100% minus processing. Time-limited: a cost-based fee could return. [RevenueCat](https://www.revenuecat.com/blog/growth/apple-anti-steering-ruling-monetization-strategy) |
| EU fee overhaul | 18 Aug 2026 | Core Technology Fee replaced with a flat 5% commission on web distribution; most developers pay 15% on in-app purchase. [Apple](https://www.apple.com/newsroom/2026/08/apple-announces-changes-for-apps-in-the-european-union/) |
| Apple Mini Apps Partner Program | 2026 | HTML5/JS mini apps in a native container qualify for **15%** commission; aimed at platform-shaped products |
| **Guideline 5.1.2(i): AI data-sharing consent** | Nov 2025 | Apps must disclose and get explicit consent before sending personal data to third-party AI providers, naming provider and data. **On-device or PCC inference skips this friction entirely** — a measurable onboarding-funnel advantage. [TechCrunch](https://techcrunch.com/2025/11/13/apples-new-app-review-guidelines-clamp-down-on-apps-sharing-personal-data-with-third-party-ai) |
| Age-verification statutes | Texas 1 Jan 2026, Utah 1 Jul 2026, Louisiana live | Compliance gate *and* moat: kids' and teen apps, previously a minefield, are now buildable solo because the primitives are OS calls |
| Loan apps capped at 36% APR; crypto exchanges added to regulated fields | 2026 | Categories to avoid at L0 |
| EU sideloading | live but narrow | Alternative marketplaces require authorisation and notarisation, and installs only work inside the EU with an EU Apple ID. **Not a viable primary channel** |
| **Sora 2 API removal** | 24 Sep 2026 | A dependency deletion 12 days out, with no announced successor. The canonical example of platform risk |

## DEMAND signals — where the money and the pull are

**Category growth**

| Segment | 2025-26 movement |
|---|---|
| Gen-AI consumer apps | 3.8B downloads (+100%), **>$5B in-app purchase (+~200%)**, 48B hours (3.6x YoY); Q2 2026 spend **+108% YoY** |
| Non-game app spend | **+33.9%**, passed games for the first time |
| Games | downloads -8.6%, Q2 2026 revenue **-4.5%** |
| Dating and social discovery | **-11% globally, -34% US** in Q2 2026 |
| Image generation | collapsed by bundling — of nine generators on the 2023 list, three remain; Midjourney fell from top-10 to #46 |

Sources: [Sensor Tower State of Mobile 2026](https://sensortower.com/blog/state-of-mobile-2026),
[TechCrunch/Appfigures](https://techcrunch.com/2026/01/14/app-downloads-declined-again-in-2025-but-consumer-spending-soared-to-nearly-156b/),
[a16z Top 100](https://www.a16z.news/p/top-100-gen-ai-consumer-apps-march).
The two data houses disagree on absolute spend ($155.8B vs $167B) for
methodological reasons; use growth rates, not levels.

**Stated demand from investors** — YC's current requests for startups name
AI-powered consumer products at billion-user scale, adaptive tutoring for children,
AI for the aging population, and human verification against deepfakes.
<https://www.ycombinator.com/rfs>

a16z's most actionable published thesis is that **marketplaces that failed before
now work**, because voice agents collapse both killers: "it might cost a few dollars
to make a match that would previously cost hundreds", and personalised
re-engagement converts one-off transactions into subscriptions. Named categories:
skilled labour, real estate, home services, professional services, healthcare
services.
<https://a16z.com/marketplaces-in-the-age-of-ai-take-two-graveyard-to-greenfield/>

This is a **tombstone-times-unlock** cell in the void map, and it is exactly what the
Tombstone Reviver operator is built to find.

## Economics — the constraints that make L3 a real gate

From RevenueCat's State of Subscription Apps 2026 (115,000+ apps, $16B+ revenue):

| Reality | Number |
|---|---|
| Median year-over-year revenue growth | **5.3%** (top decile +306%, bottom quartile -33%) |
| New apps reaching $1,000/month within 2 years | **17.3%** |
| New apps reaching $10,000/month within 2 years | **4.6%** |
| Share of subscription revenue earned by apps launched pre-2020 | **69%** (apps launched 2025+ earn 3%) |
| New subscription app launches per month | ~2,000 in Jan 2022 to **14,700+** in Jan 2026 |

**Paywall structure**, download-to-paid at day 35: hard paywall **10.7%** versus
freemium **2.1%**, and revenue per install at day 60 of $3.09 versus $0.38 — 5x
conversion and 8x revenue **with no retention penalty**. But among AI apps
specifically, freemium is 11.4 points more common among *high retainers*, and hard
paywalls are under 2% of AI apps. So: hard paywall for classic utilities, freemium
for AI products where trials are expensive but value is instant.

**The retention cliff is the defining 2026 constraint.** From RevenueCat's study of
3,519 AI apps:

| | AI apps | Non-AI |
|---|---|---|
| Trial to paid | 8.5% | 5.6% |
| Monthly revenue per payer | $18.92 | $13.59 |
| **12-month retention** | **21.1%** | **30.7%** |

And within AI apps the spread is savage: high retainers hold **13.9%** at one year
against **1.4%** for low retainers, a 10x gap. First monthly renewal: **57.9%
versus 30.2%**, and the gap narrows by the third renewal — **the first renewal is
the entire battle**. The diagnosis is the *one-and-done problem*: subscribers come
for one impressive result, get it, share it, and never return.

What separates high from low retainers, in percentage points: no trial offered
(+23.7 toward low), launched 2024+ (+20.2 toward low), subscription-only (+16.4
toward high), hybrid subscription-plus-consumables (+16.3 toward **low**), 7-day
trial (+12.7 high), freemium (+11.4 high), lower pricing (+7.3 high). Categories
that retain: **Utilities, Education**. Categories that do not: **Photo & Video,
Media & Entertainment**. **Health & Fitness shows almost no separation — habits are
built into the use case.**
<https://www.revenuecat.com/blog/growth/ai-app-retention-study>

**Trials:** 17-32 day trials convert at **42.5%** against **25.5%** for trials of 4
days or less — a 70% difference — yet **46.5% of apps use short trials**. A
persistent, exploitable mistake.

**Geography:** revenue per install at day 60 is $0.55 in North America against $0.11
in India and Southeast Asia. Target North America.

**Pricing:** higher-priced apps convert *better* — day-35 conversion 2.8% against
1.4% — and earn 5x more per payer. Median monthly $10.00, yearly $34.80.

**The acquisition arithmetic that closes paid channels.** iOS cost per install is
$5.84 (+19% year over year), 3.0x Android's $1.92; cost per *paying* user runs
$20-$80+. Median monthly revenue per payer is $8-$24. **Paid acquisition does not
work at this budget** — which is why the distribution slot in the genome is
mandatory and why an idea with no organic loop dies at L4.

**Inference cost per user:** $0.09 to $18.24 per daily active user per month at
mid-2026 list prices, a **200x spread** driven almost entirely by text-on-small-
models versus voice-on-flagship. At roughly 3% paid conversion, each payer's margin
carries ~33 users' inference bills, so blended AI cost must stay under about $0.30
per active user per month at a $9.99 price. Only on-device, cached, or small-model
stacks clear that — or Apple's free tier, which clears it trivially.
<https://inworld.ai/resources/unit-economics-of-consumer-ai-apps>

**Margin reality:** AI gross margins run 50-70% against 80-90% for traditional
software, and get *worse* with scale as inference rises as a share of spend.

## Distribution — the zero-budget channels

| Channel | Benchmark |
|---|---|
| App store search | Apple states **65% of App Store downloads follow a keyword search**; iOS converts 5.7 points higher than Play; localising into 10+ markets lifts conversion 35-50%; quarterly screenshot testing beats annual by 20-30% |
| **Store algorithm shift** | Both stores now weight **retention and stability** over raw download counts — apps with strong day-7 retention outrank competitors with more downloads. A structural advantage for a small well-retained niche app |
| Short-form video | The algorithm still surfaces zero-follower accounts if the first 3 seconds engage; realistic baseline **4-6 posts/week for 8+ weeks** before traction |
| Reddit | 116M daily actives (+20%); organic delivers 5-15% of referral traffic for consumer brands; cost per click $0.71 against $1.86-$2.04 on Meta properties if you ever pay |
| Community-led | Works, but the honest benchmark is **6-12 months** |
| Referral loops | Healthy pre-launch K-factor **0.3-0.7**; K > 1 is "rare and almost always temporary" — **do not model K > 1**. Two-sided rewards beat one-sided by 30-50%. **Cycle time dominates K**: K of 1.2 with a 3-day cycle beats K of 1.5 with a 30-day cycle |

Plus the arbitrage: 41% of top-tier apps take web revenue against 1.3% of hobby
apps, and US external payment links currently carry 0% Apple commission. Shipping a
web paywall is worth more than most growth tactics, and the window may close in
2027.

## TOMBSTONE signals — what died and why

- Of nine image generators on the 2023 consumer list, six are gone — **killed by
  bundling** into general assistants, not by competitors.
- The operative test from the postmortem literature: *"if a solo dev can rebuild your
  product in a weekend, you don't have a business."*
- Recurring cause of death: a category becomes redundant overnight when a frontier
  lab ships the feature natively.

**Confidence flag.** The widely-quoted figures "80% of AI startups will fail by end
2026", "60-70% of AI wrappers generate zero revenue", and the Sora burn-rate
anecdote are from aggregator sites and projections, not measurements. They are
excluded from the signal store. The verified version of this trap is the a16z
bundling observation above.

## What the seed evidence already implies

Stated as hypotheses to be attacked by the pipeline, not as conclusions:

1. **Category.** Utilities, Education, and Health & Fitness are the three that
   retain. Health & Fitness has the best economics and is the one category where AI
   retention does not collapse, because habit is intrinsic to the use case.
   Education is independently validated by an investor request. Photo & Video,
   Media & Entertainment, dating, games, and image generation all carry measured
   headwinds.
2. **Inference.** On-device or Apple's free Private Cloud Compute tier escapes both
   the margin trap and the new consent friction, and is the only way voice works at
   a $9.99 price point.
3. **Accumulation is the retention mechanism.** The product must build user state
   that the first renewal has something to defend. 57.9% against 30.2% first-renewal
   retention is the difference between a business and a hobby, and the one-and-done
   problem is what kills the rest.
4. **The genuinely open frontier** is the Ray-Ban Display platform: four months old,
   near-zero installed competition, an official web development path. No revenue or
   install-base data exists, so it is a reasoned bet rather than a data-backed one —
   which is exactly the kind of claim the oracle ladder exists to attack.

Every one of these is an island thesis, not an answer. That is the point: the
architecture's job is to generate against them, attack them, and make the ranking
earn itself.

---

## Sources that could not be verified

Listed because an evidence layer that hides its gaps is not an evidence layer.

- Absolute consumer-spend levels differ between data houses ($155.8B vs $167B); the
  methodology gap could not be reconciled. Growth rates only.
- No rigorous 2026 large-scale app-review-mining study exists. Subscription-fatigue
  claims, including "$200/month average consumer subscription spend", rest on vendor
  blogs. Direction is plausible; specific percentages are not citable.
- Indie-income figures circulating as "median solo developer earns $3,000-$8,000
  monthly" contradict RevenueCat's hard milestone data and should be discarded.
- No primary 2026 consumer thesis could be located for several named funds; second-
  hand characterisations are excluded.
- Cost-per-install and acquisition-cost benchmarks come from aggregators rather than
  primary attribution platforms. Ranges are consistent across sources; individual
  figures should be re-checked before anyone budgets against them.
- No data exists on Ray-Ban Display installed base, app revenue, or monetisation.
