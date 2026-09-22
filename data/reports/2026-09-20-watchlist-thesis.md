# Five-Year Investment Thesis — Ten Names

**As of 2026-09-20. Horizon: five years, to roughly 2031.**

Facts in this report trace to `data/reports/2026-09-20-full-universe-datapack.md`,
`data/reports/2026-09-20-macro-brief.md`,
`data/reports/2026-09-20-watchlist-news-brief.md`,
`data/reports/2026-09-20-full-universe-prediction.md`, and the per-ticker snapshots under
`data/raw/`, `data/scores/`, `data/predictions/` and `data/filings/` dated 2026-09-20.
Peer context comes from `uv run python tools/peers.py <TICKER>`, run 2026-09-20.

Sections labelled **Evidence** are checkable against those files. Sections labelled
**Judgement** are mine and are not in any file. Where I could not settle a question from the
evidence, it says so rather than guessing.

---

## 1. The verdict, up front

I would own four of these ten for five years, hold my nose on two, and avoid four.

**Ranking — the order I would rather own them, best first:**

| # | Ticker | Score | Model median | My rank vs score | The one-line reason |
|---:|---|---:|---:|---|---|
| 1 | NVDA | 91.3 | +18.6% | agree (1) | Best business on the list, and 28x trailing does not require the mania to continue |
| 2 | TSM | 84.9 | +9.4% | agree (2) | The only name that wins no matter which chip designer wins |
| 3 | META | 81.1 | +17.4% | agree (3) | The one AI-linked name whose revenue is not the AI capex |
| 4 | AMZN | 57.2 | +18.1% | **up 5** | Three businesses, mix shifting toward the profitable two; the C grade reads it as a retailer |
| 5 | LLY | 75.9 | +18.0% | down 1 | The only genuine diversifier here, bought at a full price with poor cash conversion |
| 6 | ASML | 78.8 | +4.8% | **down 2** | Best moat of all ten, worst price of all ten |
| 7 | AVGO | 76.0 | +7.3% | **down 2** | More expensive than NVIDIA on trailing earnings, with half the returns on capital and real debt |
| 8 | 7203.T | 46.2 | +17.1% | **up 2** | Genuinely cheap, genuinely low-return, earnings falling; the case is a re-rating bet |
| 9 | MU | 64.8 | +20.5% | down 1 | Peak-cycle earnings being valued as permanent by a model that cannot see a memory down-cycle |
| 10 | ARM | 66.4 | -16.5% | **down 3** | 60x sales and 326x earnings. The arithmetic fails even at an exit multiple nobody would pay |

I disagree with the scorecard's ordering on six of ten placements and with the model's on
five. I agree with both at the two ends — NVDA first and ARM last — and that is not laziness:
they are the only two names where business quality and price point in the same direction.

**Single strongest case: NVDA.** Not because of the growth rate, which everybody can see, but
because the price is less demanding than its reputation. At a market cap of 5.37T and a
trailing P/E of 28.1, NVIDIA's revenue merely *doubling* over five years — from $215.94B in
FY Jan-2026 to roughly $430B — with a constant 55.6% net margin and an exit at 24x still
produces about 12% a year. Tripling gets you the model's 22%. The downside case is a
multiple problem, not a business problem. Nothing else on this list has that shape.

**Single best addition to a portfolio: LLY**, which is a different answer to a different
question and I keep the two separate. Eight of these ten are the same trade (Section 3);
Lilly is one of the two that are not.

**Single weakest case: ARM.** Unambiguous, and the only one of the ten where I think the
scorecard is actively misleading. Market cap $294.35B against FY Mar-2026 revenue of $4.92B
and net income of $904M — 60x sales, 326x earnings, a 278.4 trailing P/E and a 90.2 forward
P/E. Take Arm's own 3-year revenue CAGR of 22.5%, hold it for five years, apply today's
18.4% net margin, and exit at 40x: that is a $100B company in 2031, a 66% loss, about
-19.5% a year. My arithmetic and the model's -16.5% land in the same place from different
directions. The scorecard's 66.4 comes from a balance-sheet pillar of 99.0 and a valuation
pillar of 25.1 that carries only 15% weight. A 15% weight cannot express "this price is
impossible."

**Concentration verdict: this is not a ten-name portfolio.** Details in Section 3.

---

## 2. What the two numbers are, and why they disagree so often

**Evidence.** The scorecard is `tools/score.py`: five pillars on fixed absolute bands —
growth 30%, quality 25%, cash 15%, balance sheet 15%, valuation 15%. Every company is
graded identically, which is the point and also the limit.

The model is `tools/predict.py`: 20,000 Monte Carlo paths over growth, margin and exit
multiple. The growth fade is fitted across the panel on disk. Today's fit, read from
`data/predictions/*/2026-09-20.json`:

```
next year's growth = 0.1071 + 0.1692 x this year's growth
R-squared 0.030, n = 76 company-years, se(slope) = 0.127
```

**It explains 3% of the variation.** The untrimmed fit has a slope of 0.4242 and an R-squared
of 0.289, but it is held up by four extreme points, so the trimmed fit is used and the 0.255
slope disagreement is carried as extra uncertainty. The model has never been validated out
of sample and cannot be with this data source: yfinance serves current data with no
point-in-time history, so an honest backtest is impossible. Nothing in this report is a
forecast or an expected return. The percentiles describe the spread of the assumptions.

Three mechanical facts explain nearly every disagreement between the two numbers, and a
reader who skips them will misread the whole report.

**(a) The fade has one attractor and it applies to everyone.** The fitted recursion, with the
15% pull toward a 4% terminal rate, settles at about 11.3% a year. Read the simulation's own
median ending state for all ten names:

| Ticker | Start growth | Median year-5 growth | Start net margin | Median year-5 margin | Median exit P/E |
|---|---:|---:|---:|---:|---:|
| NVDA | 60.0% | 11.6% | 55.6% | 66.7% | 21.0 |
| TSM | 34.5% | 11.6% | 44.6% | 46.3% | 23.2 |
| META | 26.1% | 11.6% | 30.1% | 44.4% | 19.4 |
| ASML | 22.0% | 11.6% | 29.4% | 32.1% | 35.9 |
| AVGO | 60.0% | 11.6% | 36.2% | 30.3% | 29.8 |
| LLY | 45.0% | 11.6% | 31.7% | 46.0% | 26.3 |
| ARM | 25.2% | 11.6% | 18.4% | 17.5% | 69.9 |
| MU | 60.0% | 11.6% | 22.8% | 28.8% | 18.4 |
| 7203.T | 6.0% | 11.6% | 7.6% | 7.2% | 11.2 |
| AMZN | 7.8% | 11.6% | 10.8% | 18.5% | 17.1 |

Every single one lands at 11.6%. That is the fitted curve, not a company. It means the model
systematically flatters slow growers (Toyota is assumed to *accelerate* from 6.0% to 11.6%)
and systematically penalises fast ones. **For Toyota specifically, an 11.6% revenue growth
rate in 2031 for a company selling roughly ten million vehicles a year into a flat global
market is not a number anyone should accept.** That single assumption is most of the gap
between its D grade and its +17.1% median.

**(b) Two of the ten have a corrupted valuation base, by design, and the exclusion is partial.**
TSM trades in USD and reports in TWD; ASML trades in USD and reports in EUR. `score.py`
therefore excluded `price_to_sales`, `ev_to_ebitda` and `fcf_yield` from their scores and
renormalized the pillars. **Their valuation pillars — TSM 81.9, ASML 61.4 — rest on 60% of
the normal inputs.** The raw values still printed in the data pack are wrong by the exchange
rate and I do not quote them: TSM's "EV/EBITDA 4.9" and "P/S 0.5", ASML's "EV/EBITDA 2657.2"
and "P/S 18.3". A further caution the tooling does not handle: `peers.py` applies no such
exclusion, so TSM's 100th-percentile price-to-sales and ASML's 0th-percentile EV/EBITDA in
the peer output are arithmetic on corrupted numbers. Ignore both.

**(c) A margin-vintage mismatch inflates two of these ten, materially.** This one is not
documented anywhere and I think it matters. The model's sales multiple is built as
`trailing_pe x net_margin_latest` — a TTM price multiple paired with the *last annual*
margin. Where TTM earnings have run far ahead of the last full year, the two disagree, and
the resulting sales multiple comes out far below the reported one. Comparing the model's
effective sales multiple against the reported price-to-sales for the eight names where both
are currency-safe:

| Ticker | Model's sales multiple | Reported P/S | Net margin implied by P/S ÷ P/E | Last annual net margin |
|---|---:|---:|---:|---:|
| META | 7.54 | 7.43 | 29.6% | 30.1% |
| 7203.T | 0.65 | 0.69 | 8.0% | 7.6% |
| LLY | 12.29 | 12.90 | 33.3% | 31.7% |
| ARM | 51.22 | 57.09 | 20.5% | 18.4% |
| NVDA | 15.62 | 17.71 | 63.0% | 55.6% |
| AVGO | 16.53 | 19.16 | 41.9% | 36.2% |
| **AMZN** | **2.20** | **3.53** | **17.3%** | **10.8%** |
| **MU** | **5.23** | **12.71** | **55.4%** | **22.8%** |

Six are close. **Micron and Amazon are not.** Micron's TTM net margin implied by its own
reported multiples is about 55%; the model projects forward from 22.8% and drifts it *up* to
28.8%, while pricing the entry off a peak-earnings multiple. Amazon's implied TTM margin of
17.3% against a reported 10.8% almost certainly reflects non-operating investment gains,
which Amazon books through net income. In both cases the arithmetic starts from a low margin
and prices off a high one, and both errors push the return the same way — up. This is exactly
the failure mode the project's own test suite exists to catch, and it is a candidate for a
new test.

**Judgement.** Where the two numbers disagree, I asked one question: which of them is looking
at the thing that decides a five-year outcome? That answer is different for each of the four
contested names and I give it plainly in each thesis, and again in Section 7.

---

## 3. Concentration: this is not ten positions

**Evidence.** The macro brief counts 17 of 37 watchlist equity tickers — about 46% — as the
same AI-capex trade seen at four points of one supply chain: design and manufacture the chip
(NVDA, AMD, AVGO, ARM, TSM, ASML, AMAT, MU), buy and deploy it (MSFT, GOOGL, AMZN, META),
build software on top (CRM, NOW, SNOW), supply the power and cooling (VRT, ETN). Adding
Samsung takes it to 18 of 37 (49%).

**Eight of my ten sit inside that basket.** Only LLY and 7203.T are outside it.

**Judgement.** "Eight of ten" is true but not precise enough to act on. The eight split into
two groups sitting on *opposite sides* of the same cycle:

- **Six sellers, whose revenue *is* the capital spending:** NVDA, TSM, AVGO, ASML, MU, ARM.
  These are not six bets. They are one revenue line observed at four points of one flow —
  NVIDIA's revenue is TSMC's revenue is ASML's revenue is Micron's revenue. A single
  hyperscaler cutting capex guidance on a Q4 2026 or Q1 2027 call hits all six in the same
  week. Owning all six is one position sized six times.
- **Two buyers, whose *cost* is the capital spending and whose revenue is something else:**
  META (advertising) and AMZN (retail, AWS, advertising). If capex stops, their free cash
  flow improves immediately while the six sellers lose their revenue line. That is a real,
  partial hedge — and it is the most useful thing this analysis produces. It is only partial:
  both would still de-rate alongside the sector even as their cash flow recovered.
- **Two outside it:** LLY (GLP-1 volume and pricing) and 7203.T (vehicles, tariffs, the yen).

So the honest statement is: **six names are one position, two more are the other side of the
same position, and two are independent.** A portfolio weighted equally across these ten
carries roughly 60% of its capital in a single capital-spending cycle, not 10% in each of ten
ideas.

Two mechanisms from the macro brief make this worse than it looks, and both are load-bearing:

1. **The buyers' capex now exceeds their cash flow, and the gap is being funded with debt,
   into a hiking Fed.** Bank of America (via Fool.com, 2026-09-06) projects hyperscaler
   aggregate free cash flow swinging from +$180bn (2025) to -$64bn (2026), -$144bn (2027) and
   -$186bn (2028) against capex near $860bn in 2026 rising toward $1.2tn in 2027. The FOMC
   raised the target to 3.75%-4.00% on 2026-09-16 (12-0, first hike since 2023), with the
   10-year at 5.00%-5.04%, its highest since 2007, and August CPI at 3.4%. Debt-funded capex
   is the most rate-sensitive kind.
2. **Chips shipped can decouple from chips earning a return.** JLL reports grid-connection
   waits in primary data-centre markets now exceed four years, with Gartner quoted forecasting
   power shortages restricting 40% of AI data centres by 2027. That means NVDA/AVGO/TSM/MU
   revenue can look fine for a year *after* the buyers' return on capital breaks. **Watch
   hyperscaler capex guidance, not semiconductor bookings.** Bookings will be the lagging
   indicator, not the leading one.

The rate shock also does not hit the eight evenly. Ranked by duration exposure among my ten:
ARM is the most exposed by a distance (forward P/E 90.2, beta 3.89), then ASML (forward P/E
28.3), then NVDA and MU (beta 2.22 each, though on much lower forward multiples). Toyota
(beta 0.34) and LLY (beta 0.50) are the least exposed, which is another way of saying the
same thing about diversification.

---

## 4. Where the scorecard is flattering a business that is riding an industry

**Evidence**, from `tools/peers.py`, run 2026-09-20. `disagreements` lists metrics where the
absolute band scores well but the sector percentile does not. Group sizes: Technology 16,
Healthcare 5, Consumer Cyclical 5, Communication Services 3, Industrials 3, Consumer
Defensive 2, Energy 2. **Four companies is the minimum for a percentile to mean anything.**

- **META is in a 3-company Communication Services group. `reliable` is false. Its percentiles
  are arithmetic without meaning and I quote none of them.** Its flagged disagreement (net
  debt/EBITDA band 92 vs peers 0) is an artifact of comparing three companies, not a finding.
- **MU — the clearest case of an absolute band flattering a commodity.** Gross margin 39.8%:
  band scores 55, sector percentile 7th. Micron's gross margin is bottom-decile in its own
  industry and the fixed band still awards it a passing grade. FCF margin 4.5%: band 35,
  percentile 0th. This is the "75% gross margin is ordinary in software and extraordinary in
  autos" problem running in reverse.
- **ARM — the bands reward a structural artifact.** FCF margin band 74 vs peers 20th (+54);
  operating margin band 61 vs peers 33rd; ROE band 48 vs peers 20th. Separately: Arm's 97.5%
  gross margin sits at the 100th percentile and means nothing — an IP licensor has almost no
  cost of goods by construction. A gross margin is not a moat measurement for this business
  model. ROIC 8.7% is the 27th percentile of its sector; that *is* a moat measurement, and it
  is below median.
- **AVGO — the largest single band/peer gap on the list.** Net debt/EBITDA 1.41x: band scores
  71, sector percentile 0th. Broadcom is the *most levered* name in a 16-company technology
  group and the absolute band reads it as comfortable. Gross margin band 90 vs peers 60th.
  ROIC 14.1% is the 53rd percentile — dead median. The 76.0 composite is riding an industry,
  not beating one.
- **TSM — flattered on two quality inputs.** Gross margin 59.9%: band 80, sector percentile
  47th. TSMC's gross margin is *below* its sector median of 63.5%, and the band reads it as
  strong. ROE band 92 vs peers 60th. TSM's real edge is process leadership and share, neither
  of which any band measures.
- **ASML — flattered on growth and margin, which is not where its case lives.** Revenue growth
  TTM 21.3%: band 76, sector percentile 33rd — *below* the sector median of 24.4%. Gross
  margin 52.8%: band 72, percentile 40th — also below median. The B+ rests partly on bands
  scoring a below-median-growth, below-median-margin business as strong. ASML's actual moat
  (EUV monopoly, ROIC 37.2% at the 87th percentile) is real; the score is not measuring it.
- **AMZN — the disagreement runs the other way.** Operating margin band 43 vs peers 75th;
  revenue CAGR band 64 vs peers 100th. The scorecard is *penalising* Amazon relative to its
  sector. But note the sector: Consumer Cyclical here is Amazon, Toyota, LVMH, Alibaba and
  Tesla. That clears the four-company threshold and is still not a peer group in any economic
  sense. Statistical sufficiency is not economic comparability, and the `reliable` flag cannot
  tell you that.
- **7203.T — same group problem, worse.** Gross margin 16.7% at the 0th percentile of a group
  containing Amazon at 50.3%. Comparing an automaker's gross margin to a cloud company's is
  not a comparison.
- **NVDA — barely anything to flag,** which is itself informative. One disagreement (net
  debt/EBITDA band 95 vs peers 53rd). And a genuinely counterintuitive fact worth surfacing:
  **NVIDIA's price-to-sales of 17.7 is the 33rd percentile of its own sector.** Two-thirds of
  the technology names tracked here are more expensive on sales than NVIDIA is.
- **LLY** — one disagreement (net debt/EBITDA band 76 vs peers 33rd) in a 5-company Healthcare
  group. Its FCF margin at the 25th percentile and dividend yield at the 0th are real.

---

## 5. A documentation gap that makes some of these look safer than others

**Evidence.** Risk-factor coverage in this data pack is badly uneven, and the unevenness
tracks filing regime, not risk:

| Ticker | Item 1A / risk-factor evidence available |
|---|---|
| NVDA | 10-K filed 2026-02-25, 115,093 characters captured, 18 factors |
| META | 10-K filed 2026-01-29, 119,997 characters, 18 factors |
| LLY | 10-K filed 2026-02-12, 77,526 characters, 12 factors |
| AVGO | 10-K filed 2025-12-18, 90,609 characters, 18 factors |
| MU | 10-K filed 2025-10-03, 102,745 characters, 18 factors |
| ARM | 20-F filed 2026-05-26, 120,000 characters, 18 factors |
| TSM | 20-F filed 2026-04-16, **23,564 characters, 3 factors** |
| ASML | **No risk-factor section parsed** — "no clear end boundary was found" |
| AMZN | **No 10-K in the collected filings and no risk-factor section at all** |
| 7203.T | **No filings collected. Non-SEC filer; there is no Item 1A for Toyota.** |

**Judgement.** Four of my ten have little or no disclosed-risk evidence in this pack, and
Toyota has none at all. That is an absence of evidence, not evidence of safety. Toyota's
tariff exposure — ¥1.4 trillion in FY2026, producing a -1.4% North America operating margin
and its first North America loss in sixteen years — is arguably the most concrete
company-specific risk on this entire list, and it appears nowhere in a filing I can read. TSM's
three captured risk factors do not mean Taiwan is a small risk. I weight the six well-documented
names' risk sections accordingly and lean on the news brief for the other four, and a reader
should not mistake filing volume for risk magnitude.

Separately: the data pack shows "No news collected" for ASML, MU, ARM, AMZN and 7203.T. The
pack was generated at 15:34 and the news brief at 15:43 on 2026-09-20; the news for those five
was fetched in between. Their news evidence comes from the brief (103, 180, 108, 189 and 157
articles respectively), not from the pack.

---

## 6. The ten theses

---

### NVDA — NVIDIA Corporation · Score 91.3 · Model median +18.6% · My rank 1

**The judgement, first.** Worth owning. NVIDIA is the best business on this list by every
measure that survives scrutiny, and — contrary to the reflex — the price is not the problem.
The problem is that its revenue line is four phone calls wide. Its own FY2026 10-K says one
customer was 22% of revenue and another 14%. That is the thing that decides the five years,
not the growth rate.

**Evidence.** Price $222.27, market cap 5.37T, -6.0% off the 52-week high, analyst target
$327.70 (59 analysts). FY Jan-2026: revenue $215.94B (from $130.50B), net income $120.07B,
FCF $96.68B. Net margin 55.6%, operating margin 60.4% trending +12.74pp/yr, gross margin 71.1%,
ROIC (est.) 62.1%, ROE 117.2%. Net cash $51.52B. Trailing P/E 28.1, forward P/E 14.2, P/S 17.7,
dividend yield 0.45%, beta 2.22. Pillars: growth 100.0, quality 98.5, cash 87.7, balance sheet
94.6, valuation 62.1, all at 100% coverage. Model p05/median/p95: +3.0% / +18.6% / +37.7%,
P(loss) 3%. Deciding assumption: exit multiple, 12.0 points of swing.

From the news brief: four customers ~61% of Q3 FY2026 revenue on third-party aggregation, a
rising trend; "zero percent" China AI-chip share per Jensen Huang (2026-05); the 70% FY2028
revenue growth guide is the company's own; DOJ probe of the ~$17-20B Groq licensing structure
(reported 2026-09-10). From the macro brief: NVIDIA disclosed over $540bn in financing
arrangements during 2026 and announced platforms with Apollo, BlackRock, Blackstone,
Brookfield, Goldman Sachs and KKR to mobilise $500bn+.

**The mechanism of growth.** NVIDIA sells accelerated-computing systems — GPUs plus the
networking and the CUDA software layer that makes them useful — to about a dozen hyperscalers,
AI labs and sovereign programmes, who buy because training and serving frontier models is
compute-bound and NVIDIA's platform is the one their code already runs on. What stops a
competitor is not the silicon; AMD's silicon is competitive. It is that a decade of models,
kernels and tooling are written against CUDA, and that NVIDIA ships a rack-scale system while
competitors ship a chip. Switching cost is measured in engineer-years.

**What has to be true.** Checkable in 2028:
1. Aggregate hyperscaler capital spending stays at or above its 2026 level (~$860bn, BofA)
   in every year through 2029.
2. NVIDIA's two largest direct customers are no more than 40% of revenue combined in the
   FY2028 10-K (they were 36% in FY2026).
3. Revenue reaches at least $430B by FY Jan-2031 — a doubling, not a tripling.
4. Gross margin stays above 65% (71.1% today).

**The bear case, made properly.** NVIDIA's customers are spending more than they earn. The
gap is being financed, increasingly by structures NVIDIA itself sits inside — $540bn of
financing arrangements in one year, plus an investment and partnership agreement with OpenAI
that the 10-K discloses as *not yet signed*. When a supplier finances its customer's purchase
of its own product, revenue growth and credit risk stop being separable. NVIDIA's own new
risk factors say exactly this in two places: "Commercial arrangements expose us to
counterparty risks" and "Our investment portfolio contains industry sector concentration
risks." A single large AI lab failing to raise its next round does not cost NVIDIA one
quarter of orders; it costs a receivable, an equity mark, and the forward order book of
everyone who was watching. Add the grid: if 40% of AI data centres are power-constrained by
2027 (Gartner via industry press), the buyers discover that deployed compute lags purchased
compute, and the first thing they cut is next year's order. And run the arithmetic on the
base case honestly: revenue tripling to ~$670B in 2031 is 78% of the *entire* 2026
hyperscaler capex pool and 56% of the 2027 projection. NVIDIA today captures about 25% of that
pool. The base case needs share to roughly double, or the pool to keep growing well past
2027 consensus, or both.

**Valuation — what is priced in.** At 28.1x trailing on an implied TTM net income of about
$191B (market cap divided by trailing P/E — an inference, not a reported figure), the market
is asking for roughly 12-13% a year in earnings growth to deliver 10% a year at a 25x exit.
For a company whose net income CAGR is 201.8%, that is not a demanding hurdle. Decomposing
the base case: revenue triples (index 3.10), the margin is held flat at 55.6% (score.py's
ceiling blocks expansion), and the exit is 24.3x versus 28.1x today — so the whole return is
the revenue call. Halve the revenue call to a doubling and keep 24x: about 12% a year. Halve
it and compress the multiple to 18x: about 5% a year. **The multiple matters more than the
growth, which is the opposite of the usual story about this stock.** I would note the model's
simulation lets NVIDIA's net margin expand to a median 66.7% — the ceiling is
`max(0.60, margin x 1.20)`. A 66.7% net margin at this scale would be unprecedented and I do
not accept it; score.py's flat-margin treatment is the right one.

**Risks that would end it, ranked.** (1) Customer concentration converting into a demand air
pocket — its own 10-K discloses the 22%/14% figures. (2) The vendor-financing complex taking a
credit loss. (3) Export controls; the January 2026 regime gives a 25% tariff and a 50% volume
cap on H200-class chips to China, with no deliveries as of 2026-08-19 — this is mostly priced
as a floor already reached. (4) The DOJ/Groq probe extending to a structural remedy on
licensing-style acquisitions, which is the mechanism NVIDIA now uses to extend its platform.
Priced: China, deceleration (the 70% FY2028 guide is the company's own). Not priced: a
counterparty credit event.

**What would change my mind.** Up: two consecutive quarters of hyperscaler capex guidance
*raised* alongside utilisation commentary showing deployed compute keeping pace with
purchased compute. Down: any hyperscaler guiding 2027 capex flat or lower; a disclosed
impairment on an AI-related receivable or equity stake; top-two customer concentration above
40%.

---

### TSM — Taiwan Semiconductor · Score 84.9 · Model median +9.4% · My rank 2

**The judgement, first.** Worth owning, and the ordering against NVIDIA is closer than the
scores suggest. TSMC is the only name here that is indifferent to *which* chip designer wins.
If NVIDIA loses share to AMD, or to Google's TPUs, or to Broadcom's XPUs, or to Amazon's
Trainium, every one of those parts is fabricated by TSMC. That is a structurally safer
revenue line than NVIDIA's. The price is what holds it at second rather than first: per unit
of earnings, TSMC is *more* expensive than NVIDIA today.

**Evidence.** Price $434.67 (ADR), market cap 2.25T USD, -9.3% off the high, analyst target
$552.26 (20 analysts). 2025 (Dec): revenue NT$3.81T (from NT$2.89T), net income NT$1.70T, FCF
NT$992.38B. Gross margin 59.9%, operating margin 50.8% (trend +0.70pp/yr), net margin 44.6%,
ROIC (est.) 23.9%, ROE 40.0%. Net cash NT$2.06T. Trailing P/E 32.5, forward P/E 19.8, dividend
yield 0.94%, beta 1.25. Pillars: growth 83.6, quality 83.6, cash 83.4 (80% coverage), balance
sheet 93.9, **valuation 81.9 at 60% coverage**. Model p05/median/p95: -7.1% / +9.4% / +27.9%,
P(loss) 17%.

**Currency caution, stated where I use it:** TSM trades in USD and reports in TWD, so
`price_to_sales`, `ev_to_ebitda` and `fcf_yield` were excluded and the pillars renormalized.
The valuation pillar of 81.9 rests on forward P/E, trailing P/E and PEG only. **An 81.9
"cheap" reading is thinner than it looks, and the P/S of 0.5 and EV/EBITDA of 4.9 printed in
the data pack are wrong by the TWD/USD rate.** I use neither.

From the news brief: no geopolitical escalation in 180 days; US commitment raised to roughly
$265-300B cumulative (from $165B in 2025), a 10-year Amkor advanced-packaging partnership in
Arizona, a Germany JV milestone (2026-09-15); August monthly revenue +53% YoY, June +68%;
TSMC said in September 2026 it is "unable to keep pace with the AI boom despite fivefold
expansion." Taiwan added 279 entities to its own strategic-goods watch list — a second,
distinct export-control channel that the China-invasion framing usually misses.

**The mechanism of growth.** TSMC sells fabrication capacity at the leading edge to
fabless designers who cannot build their own. They keep buying because a 2nm fab costs tens
of billions and takes years, and because TSMC's yield at each new node is the best available —
a designer who fabs elsewhere ships a worse chip later. What stops a competitor is capital,
time and yield learning simultaneously: Samsung Foundry and Intel Foundry have the first two
and not the third.

**What has to be true.**
1. Revenue roughly doubles, NT$3.81T (2025) to NT$7.5-8T by 2030 — which is what the
   announced capacity plans imply.
2. Gross margin stays above 55% despite the overseas mix. Arizona, Kumamoto and Dresden are
   structurally lower-margin than Taiwan fabs.
3. Intel Foundry and Samsung Foundry combined stay under 15% of leading-edge logic.
4. No Taiwan Strait event.

**The bear case.** Two of them, and they are unrelated. The first is margin: TSMC is spending
$265-300B in the United States for political reasons, at costs it has said repeatedly are
higher than Taiwan's, and every dollar of that revenue mix dilutes the 59.9% gross margin that
the whole quality case rests on. Note that 59.9% is already *below* its sector's 63.5% median
(peers, 47th percentile) — the absolute band scores it 80. The second is Taiwan, and the honest
statement is that it is unpriceable. The news brief's finding that nothing moved in either
direction in 180 days is a statement about the news, not about the risk. A quarantine short of
open conflict — shipping and insurance disruption, not invasion — would close the return
question in a week, and no analysis on this page would have helped.

**Valuation.** Trailing P/E 32.5 on a 44.6% net margin means you pay more per unit of earnings
than for NVIDIA at 28.1x on a 55.6% margin. Decomposing the base case: revenue index 2.09
(growth 34.5% fading to 4%), margin 44.6% to 45.0%, exit 24.7x versus 32.5x today. So about
three-quarters of the revenue doubling is consumed paying down the entry multiple, leaving
11.0% a year. **The model's +9.4% median is, in my view, the more honest of TSM's two
numbers.** The scorecard's 84.9 is right about the business and its valuation pillar is
running on partial information.

**Risks.** (1) Taiwan. (2) Gross margin dilution from geographic diversification — the
structural cost of the hedge against risk (1). (3) A large customer dual-sourcing leading edge
at volume. (4) Taiwan's own tightening export regime. The 20-F's three captured risk factors —
"Since 2018, political and trade tensions among a number of the world's major economies have
been on the rise" and the "P.R.C. fab's acquisition of certain manufacturing tools" — are
thin, and I said so in Section 5.

**What would change my mind.** Up: gross margin holding above 58% through two years of rising
overseas mix, which would mean the political capex is not the margin drag it looks like. Down:
gross margin under 50%; any leading-edge customer publicly qualifying a second foundry at
volume.

---

### META — Meta Platforms · Score 81.1 · Model median +17.4% · My rank 3

**The judgement, first.** Worth owning, and the reason is structural rather than financial: of
the eight names here tied to the AI capital cycle, META is one of only two whose *revenue* is
not the capital cycle. If AI capex stops tomorrow, Meta's free cash flow improves. That is a
different risk shape from the six sellers, and in a basket this correlated it is worth paying
for. But the model's +17.4% depends on a margin expansion that Meta's most recent full year
already contradicted, and my own number is lower.

**Evidence.** Price $665.75, market cap 1.70T, **-15.3% off the 52-week high**, analyst target
$755.28 (56 analysts). 2025: revenue $200.97B (+22.2%), net income $60.46B — **down** from
$62.36B in 2024 — FCF $46.11B, down from $54.07B. Total debt $83.90B, up from $49.06B in one
year. Gross margin 82.0%, operating margin 41.4% (trend +5.74pp/yr), net margin 30.1%, ROIC
(est.) 23.8%, R&D intensity 28.5%. Trailing P/E 25.1, forward P/E 19.0, P/S 7.4, dividend yield
0.32%, beta 1.24. Pillars: growth 84.8, quality 89.8, cash 78.6, balance sheet 85.2, valuation
57.6 (70% coverage). Model p05/median/p95: +1.5% / +17.4% / +36.0%, P(loss) 4%.

**Peer context: none.** META is in a 3-company Communication Services group. `reliable` is
false. I quote no percentile for it.

From the news brief: 2026 capex guidance raised twice, to $125-145B then $130-145B; Q2 2026
free cash flow reported at **$784M**; Meta's own claim of incremental ROIC above 20% on recent
AI investment (company-provided, not independently audited); a $17-18B child-safety settlement
with state attorneys general agreed 2026-08-26, with thousands of similar suits allowed to
proceed per an August 2026 appeals ruling.

**The mechanism of growth.** Meta sells auctioned advertising impressions against the attention
of roughly three billion daily users across Facebook, Instagram, WhatsApp and Threads. Revenue
is impressions times clearing price, and the clearing price is set by advertisers bidding
against each other, so improvements in targeting accrue to Meta rather than to advertisers.
What stops a competitor is that the auction gets better as it gets bigger — more advertisers
bidding on the same impression raises the price — and no one else has both the inventory and
the identity graph at this scale.

**What has to be true.**
1. Family-of-Apps revenue compounds at least 15% a year through 2030, $200.97B to ~$404B.
2. Net margin stays at or above 28%. This is the crux: $130-145B a year of capex becomes
   depreciation, and depreciation lands on the operating margin.
3. Free cash flow recovers above $40bn a year by 2028. It was $46.11B in 2025 and $784M in
   one quarter of 2026.
4. No second settlement at the $17bn scale.

**The bear case.** Meta is spending 65-72% of its revenue on capital expenditure. In 2025, net
income fell while revenue grew 22% and debt rose 71%. The Q2 2026 free cash flow of $784M is
not a rounding error; it is the ad business's entire cash generation being consumed by the AI
buildout. The company's answer is a >20% incremental ROIC figure that it computes itself and
that no third party has audited, and the news brief is right to flag the possibility that
legacy ad cash flows are being attributed to AI. Mark Zuckerberg's control of the company means
there is no mechanism by which shareholders can stop this. And the model's own base case is
the tell: it assumes net margin rises from 30.1% to 44.4% by 2031, extrapolating an operating
margin trend of +5.74pp/yr that was measured across the recovery from the 2022 "year of
efficiency" trough — a trend the 2025 result already reversed. **Run the same arithmetic with
the margin flat at 30.1% and the model's own 20.4x exit and you get about 8% a year, not
17.4%.** That is my base case for Meta, not the model's.

**Valuation.** At an unchanged 25.1x trailing multiple, Meta returns whatever earnings do.
Revenue compounding 15% with a flat 30% margin is 15% a year; the same with the multiple
de-rating to 20x is about 8%. So **my range for META is 8-15% a year, and the whole spread is
the margin and the multiple, not the revenue.** What you are actually buying at 19x forward is
an advertising business growing in the mid-20s, with the AI spend as an attached liability of
uncertain value. That is a reasonable price for the ad business alone. The optionality is
close to free, which is the entire case.

**Risks.** (1) Capex-driven margin compression that does not reverse — the only one that
matters. (2) A regulatory remedy that changes the product rather than charging a fine; the
2026-08-26 settlement required platform changes for minors, and a second wave of state suits
is live. (3) Reality Labs, which the 10-K flags twice: "We may not be successful in our
Reality Labs strategy and investments." (4) The AI initiatives themselves — "We may not be
successful in our artificial intelligence initiatives." Priced: the settlement (bounded,
agreed). Not priced: net margin settling in the mid-20s.

**What would change my mind.** Up: free cash flow back above $15bn in a single quarter with
capex guidance flat — that would mean the buildout has a top. Down: 2027 capex guided above
$145B with FCF still near zero; net margin below 25% in any full year.

---

### AMZN — Amazon.com · Score 57.2 · Model median +18.1% · My rank 4 · **CONTESTED**

**The judgement, first.** Worth owning, and the C grade is the more misleading of the two
numbers — but the model's +18.1% is too high for a reason nobody has flagged. The scorecard
reads Amazon as a low-margin retailer with terrible cash conversion. It is a low-margin
retailer bolted to a cloud business and an advertising business, and the five-year return is
entirely a question of mix. The right number is neither 57.2 nor +18.1%; it is a
margin-expansion bet at a full price, worth about 9-10% a year on defensible assumptions.

**Which number is measuring the thing that will matter: the model, but not for its stated
reason.** The scorecard's C is driven by a cash pillar of 22.0 (FCF yield 0.28%, FCF collapsed
from $32.88B in 2024 to $7.70B in 2025) and a growth pillar of 56.2 at 80% coverage, dragged by
a forward EPS growth figure of **-16.5%**. Both are capex artifacts. Amazon is spending $220B
in 2026; free cash flow is the difference between operating cash flow and that spend, so a
company mid-buildout scores terribly on cash by construction. The model is right that reported
FCF understates earnings power. It is wrong about how much.

**Evidence.** Price $253.71, market cap 2.74T, -11.7% off the high, analyst target $328.22 (59
analysts). 2025: revenue $716.92B (+12.4%), operating income $79.97B, net income $77.67B, FCF
$7.70B. Operating margin 11.2% with a trend of **+3.07pp/yr**; net margin 10.8%; ROIC (est.)
13.3%; ROE 30.6%. Net debt $29.96B, current ratio 1.03. Trailing P/E 20.4, **forward P/E 24.5
— higher than trailing**, P/S 3.5, no dividend, beta 1.44. Pillars: growth 56.2 (80%), quality
62.7, cash 22.0 (65%), balance sheet 71.7, valuation 70.6. Model p05/median/p95: +2.5% /
+18.1% / +36.4%. **No risk-factor section and no 10-K in the collected filings.**

Operating income trajectory: $12.25B (2022), $36.85B (2023), $68.59B (2024), $79.97B (2025).

From the news brief: AWS AI/chip business at roughly a $25B annual run rate (Q2 2026 call);
2026 capex raised to $220B **citing higher memory costs** — the same DRAM spike that is
inflating Micron's profits is inflating Amazon's buildout bill; FTC and 22 states sued on
2026-08-31 alleging roughly $20B taken via undisclosed ad-auction surcharges; Amazon Supply
Chain Services launched May 2026 as a direct entry against UPS and FedEx.

**The mechanism of growth.** Three businesses in one P&L. Retail is a low-margin logistics
operation that generates float and traffic. AWS rents compute and storage to enterprises who
keep paying because their data has gravity and their applications are written against AWS
primitives. Advertising sells placement at the point of purchase intent — the single most
valuable ad inventory that exists, because the user has already decided to buy something. The
five-year return comes from the second and third growing faster than the first, which mixes
consolidated margin upward without anything in retail having to improve.

**The correction the model needs.** Amazon's trailing P/E of 20.4 implies a TTM net margin of
17.3% (P/S 3.53 divided by P/E 20.41) against the 10.8% it actually reported for 2025. Amazon
marks equity stakes through net income, so that gap is very likely non-operating gains. The
model builds its sales multiple as `trailing_pe x net_margin_latest` = 2.20, versus a reported
3.53 — it is pricing the entry at about 62% of the real multiple. Redo the same arithmetic
consistently at a 3.53 sales multiple (which raises the exit anchor too, partially offsetting):
the base case falls from 13.0% a year to about **9.5%**. On an honest operating basis the entry
is roughly 33x, not 20x.

**What has to be true.**
1. AWS revenue growth stays above 20% a year through 2029.
2. Consolidated operating margin reaches 15% or better by 2030 (11.2% today). This is the
   whole thesis.
3. 2026's $220B capex is a peak, not a step — capex flat or lower in 2027.
4. The FTC ad case ends in money rather than a structural remedy to the auction.

**The bear case.** The operating-margin trend of +3.07pp a year, which carries the entire
model result, was earned by fixing an over-built fulfilment network — a one-time repair that
cannot repeat. The next leg has to come from mix, and mix is now fighting a $220B capex bill
whose depreciation lands directly on operating income. Meanwhile the highest-margin piece of
the mix — advertising — is the exact business the FTC and 22 states are attacking, alleging
$20B of undisclosed surcharges. If that ends in a remedy to how the auction works rather than
a cheque, the margin expansion loses its best engine. And free cash flow of $7.70B on a 2.74T
market cap means that for now, an owner of Amazon receives nothing: no dividend, no buyback of
consequence, and the earnings are being reinvested at a return the company does not disclose
by segment. Nobody outside Amazon knows what fraction of $220B is AWS versus fulfilment, and
the news brief flags that as unanswered.

**Valuation.** At an honest ~33x operating earnings, a 10% annual return with a 25x exit
requires net income to compound about 17.8% a year — $77.67B to roughly $176B by 2031. Amazon's
net income went from $30.43B (2023) to $77.67B (2025), so 17.8% is a sharp deceleration from
the recent path but demanding in absolute terms. **Verdict: worth owning, expect something like
9-10% a year, and treat the model's 18.1% as an artifact of a too-low entry multiple.**

**Risks.** (1) Operating margin stalling near 11% while capex keeps rising. (2) An FTC
structural remedy on the ad auction. (3) AWS growth decelerating below 15% as enterprises
optimise. (4) The absence of any risk-factor disclosure in this pack, which means I am
reasoning about Amazon on press and financials alone.

**What would change my mind.** Up: operating margin above 13% with capex guided flat. Down:
operating margin flat for two consecutive years; the FTC case surviving a motion to dismiss
with structural relief on the table.

---

### LLY — Eli Lilly · Score 75.9 · Model median +18.0% · My rank 5

**The judgement, first.** Worth owning, and the reason is portfolio construction as much as
company quality: it is one of only two names here whose five-year outcome has nothing to do
with data-centre capital spending. The company itself is excellent and concentrated — 56% of
2025 revenue in two drugs — and it is bought at a full price with the worst cash conversion of
the ten. I would own it smaller than the four above it.

**Evidence.** Price $1,152.93, market cap 1.03T, -10.8% off the high, analyst target $1,325.39
(29 analysts, "buy" — the least enthusiastic consensus among the ten). 2025: revenue $65.18B
(+44.7%), operating income $29.70B, net income $20.64B, **FCF $5.96B**. Gross margin 83.0%,
operating margin 45.6% (trend +5.72pp/yr), net margin 31.7%, **FCF margin 9.2%, FCF yield
0.58%, FCF CAGR 9.0%** against a net income CAGR of 49.0%. ROIC (est.) 34.0%, ROE 102.3%. Net
debt $35.23B (1.11x EBITDA), total debt $42.50B up from $16.24B in 2022. Trailing P/E 38.8,
forward P/E 24.4, dividend yield 0.60%, **beta 0.50**. Pillars: growth 95.9, quality 96.5,
**cash 43.4**, balance sheet 58.4, valuation 51.4. Model p05/median/p95: +1.9% / +18.0% /
+37.0%. News lean over 60 days: 9 positive, 19 negative, 65 neutral — the only one of the ten
with a negative headline skew.

From the 10-K (filed 2026-02-12), the company's own words: Mounjaro and Zepbound "accounted for
56 percent of our total revenues in 2025," six products together 82%. And: "We derive a
significant percentage of our total revenue from relatively few products." That sentence is
boilerplate in most filings and is not boilerplate here.

From the macro brief: Lilly and Novo signed most-favored-nation deals cutting direct-to-consumer
GLP-1 pricing to $350/month from $1,000-1,350, and Medicare/Medicaid pricing to about
$245/month; Medicare covers obesity treatment for the first time via a Section 402
demonstration from 2026-07-01; all 50 states signed onto a Medicaid MFN plan as of 2026-09-18,
two days before this snapshot. Lilly committed $27bn to domestic manufacturing.

From the news brief: Foundayo (Lilly's oral GLP-1) "has captured over 30% of new US patients on
oral weight-loss drugs" (Reuters, 2026-09-14); an analyst downgrade the same week citing
"obesity market overestimation"; roughly $25bn across about ten acquisitions in 2026; share
loss to generics in India.

**The mechanism of growth.** Lilly sells tirzepatide, a GLP-1/GIP dual agonist, under two brand
names for two indications, to patients and payers who keep buying because the drug works and
because stopping it reverses the effect — chronic dosing, not a course of treatment. What stops
a competitor is composition-of-matter patents running into the mid-2030s (outside this window),
peptide manufacturing capacity that takes years to build, and clinical data no one else has.
Novo is the only comparable competitor and both are supply-constrained.

**What has to be true.**
1. Incretin revenue grows despite a roughly two-thirds cut to list price. Volume must more
   than triple to hold the revenue line. This is unresolved and I will not pretend otherwise.
2. Free cash flow above $25bn by 2029 (from $5.96B in 2025). Without this the reported
   earnings are notional.
3. Foundayo expands the obesity market rather than cannibalising higher-margin injectable
   revenue. **The news brief flags that nobody has published Foundayo's gross margin relative
   to Zepbound's — the one number that would settle it.**
4. At least one non-incretin franchise passes $5bn in annual revenue, cutting the 56%.

**The bear case.** Lilly earned $20.64B and converted $5.96B of it to cash. The gap is capital
expenditure and acquisitions — $27bn of committed domestic manufacturing plus ~$25bn of deals
in one year — which means an owner is funding the growth and receiving a 0.60% yield for it.
Now cut the price of the product by two-thirds. The MFN arithmetic is not a headwind that can
be modelled away: a $1,000/month drug at $350/month needs volume up 2.9x just to stand still,
and Medicare's new coverage is the offsetting volume channel but nobody has sized it. If volume
undershoots, the operating leverage that produced a 45.6% operating margin reverses violently,
because the capacity is already built. Meanwhile Lilly is cannibalising its own injectable
franchise with its own pill, at an unknown margin, while losing share to generics wherever IP
is weak. And at 38.8x trailing you are paying a growth multiple for a business with one product
line and a government actively setting its price.

**Valuation.** At 38.8x trailing on an implied ~$26.6B of TTM net income, holding the market cap
flat at a 25x exit in 2031 requires net income to double to $41.2B — 14.8% a year. A 12% annual
total return at 25x requires $72.6bn, or 28.6% a year in earnings growth, against a 49% recent
CAGR. So the price demands a substantial deceleration but not a stall. **That is a fair
price, not a cheap one, and it prices the MFN cut as survivable.** If the volume response
disappoints even modestly, the multiple and the earnings compress together.

**Risks.** (1) The MFN volume-versus-price question, which the macro brief explicitly declines
to call and neither will I. (2) A class-wide safety signal in incretins — the 10-K's
"Pharmaceutical products can develop safety or efficacy concerns" is the highest-consequence
line in the filing. (3) CMS extending MFN pricing beyond Medicare/Medicaid into commercial
plans. (4) Cash conversion never improving. Priced: the announced MFN deals. Not priced: the
2026-09-18 all-50-states Medicaid news, two days old at snapshot and possibly not in guidance.

**What would change my mind.** Up: two quarters of incretin revenue growth *after* MFN pricing
takes effect, plus FCF above $10bn in a single quarter. Down: incretin revenue declining
year-over-year in any quarter; a safety signal; commercial-plan MFN.

---

### ASML — ASML Holding · Score 78.8 · Model median +4.8% · My rank 6

**The judgement, first.** The best business of all ten and the one I would least like to buy at
this price. ASML is a literal monopoly — no one else makes an EUV lithography machine — and it
is trading at 57.8x trailing earnings. This is the most common way a thesis that is right about
the company is wrong about the return, and the model's arithmetic makes the point cleanly: even
assuming an exit multiple of 36.5x, which is generous, the base case is +3.7% a year and 31% of
simulated paths lose money. I would want 35x trailing, not 58x.

**Evidence.** Price $1,679.92, market cap $645.26B, **-16.0% off the high**, analyst target
$2,137.63 (16 analysts). 2025: revenue €32.67B (+15.6%), operating income €11.30B, net income
€9.61B, FCF €11.03B. Gross margin 52.8%, operating margin 34.6% (trend +1.08pp/yr), net margin
29.4%, **ROIC (est.) 37.2%**, ROE 53.9%. Net cash €8.93B, current ratio 1.33. Trailing P/E 57.8,
forward P/E 28.3, dividend yield 0.54%, beta 1.36. Pillars: growth 77.2, quality 85.5, cash 80.9
(80%), balance sheet 86.4, **valuation 61.4 at 60% coverage**. Model p05/median/p95: -10.7% /
+4.8% / +22.0%, **P(loss) 31%**. Base-case exit P/E 36.5; median simulated exit 35.9.

**Currency caution:** ASML trades in USD and reports in EUR, so `price_to_sales`,
`ev_to_ebitda` and `fcf_yield` were excluded. **The valuation pillar of 61.4 rests on 60% of
its normal inputs.** The EV/EBITDA of 2657.2 and P/S of 18.3 in the data pack are corrupted by
the EUR/USD rate and I use neither. The peer output's 0th-percentile EV/EBITDA is likewise
meaningless.

Revenue history matters here: €21.17B (2022), €27.56B (2023), **€28.26B (2024, +2.5%)**, €32.67B
(2025). There is a flat year two years ago. **No risk-factor section was parsed from the 20-F.**

From the news brief: The Information reported 2026-07-27 that a Chinese state-backed company has
begun manufacturing an immersion DUV machine — about 5 machines planned in 2026 and 20 in 2027,
against ASML's 131 immersion systems delivered in 2025, reportedly lagging by four generations,
headed to SMIC, Hua Hong and CXMT. The stock fell as much as 8%. Separately, ASML "won over"
TSMC and Samsung for new EUV machines in September 2026, reversing an April 2026 report that
TSMC had declined its latest tools.

**The mechanism of growth.** ASML sells the machines that print circuits onto silicon. Every
leading-edge logic and DRAM chip in the world is patterned by an ASML EUV scanner, because no
other company can make one — the optics supply chain (Zeiss), the tin-plasma light source and
three decades of accumulated process knowledge are not replicable on a five-year timescale.
Revenue is machine sales plus a growing, higher-margin installed-base service and upgrade
annuity. Customers keep buying because a node shrink without EUV is not possible.

**What has to be true.**
1. Revenue compounds above 15% a year — €32.67B to €66B+ by 2030.
2. The multiple holds near 30-35x trailing. At today's 57.8x, simply reverting to 35x is a
   39% drawdown before the business does anything.
3. High-NA EUV converts from tool placements into volume orders.

**The bear case.** ASML had a +2.5% revenue year in 2024, two years ago. Lithography orders are
lumpy, customer-concentrated and tied to a handful of fab construction decisions that are
themselves tied to the AI capex cycle everything else here depends on. At 57.8x trailing, a
single flat year does not produce a flat stock; it produces a de-rating, because a 58x multiple
is a statement that growth is uninterrupted. Consider also that the peer check shows ASML's TTM
revenue growth of 21.3% is *below* its sector median of 24.4% and its gross margin of 52.8% is
below the 63.5% median — the B+ composite is partly bands scoring a below-median business as
strong. Then add China: the addressable DUV revenue there now has an expiry date, even if that
date is beyond this window. And note the model's own honesty — it *already* assumes a de-rating
from 57.8x to 35.9x and still cannot produce a return, because the growth assumption has to
carry the whole multiple compression.

**Valuation.** This is the cleanest "great business, punishing price" case on the list. At
28.3x forward, ASML needs revenue growth above 15% sustained *and* a terminal multiple near 30x.
Either one slipping takes the five-year return to zero or below. The model gives a 31% chance of
losing money over five years, which is the highest of the eight non-ARM names here.

**Risks.** (1) A single flat revenue year triggering multiple compression — the highest
probability path to a poor outcome, and it has precedent in 2024. (2) The AI capex cycle turning,
which reaches ASML last and hurts longest because fab decisions are multi-year. (3) China DUV
substitution, real but distant. (4) The 5% 10-year Treasury, which hits a 28x forward multiple
harder than a 14x one. **Priced: China DUV (the stock fell 8% on the report). Not priced: a flat
year.**

**What would change my mind.** Up: the price. At 35x trailing I would own this ahead of AVGO,
MU and Toyota without hesitation. Down: a quarter of declining bookings; High-NA orders slipping
into 2029.

---

### AVGO — Broadcom · Score 76.0 · Model median +7.3% · My rank 7

**The judgement, first.** I would not own it, and this is where I disagree with the scorecard
most among the names it rates highly. A 76.0 composite and a growth pillar of 91 describe a
company that is riding an acquisition and an industry rather than beating either. Broadcom is
*more expensive than NVIDIA* on trailing earnings, with less than a quarter of its returns on
capital, a declining operating margin trend, real net debt, and a custom-ASIC franchise that
just lost a socket at its largest reported customer.

**Evidence.** Price $357.61, market cap 1.71T, **-27.8% off the 52-week high** — the largest
drawdown of the ten. Analyst target $531.85 (47 analysts). FY Oct-2025: revenue $63.89B (+23.9%),
operating income $26.07B, net income $23.13B, FCF $26.91B. Gross margin 67.8%, operating margin
40.8% **with a trend of -2.35pp/yr**, net margin 36.2%, **ROIC (est.) 14.1%**, ROE 44.2%. **Net
debt $48.96B, 1.41x EBITDA**; total debt $65.14B. **Trailing P/E 45.7** versus forward 18.4;
dividend yield 0.73%, beta 1.46. Pillars: growth 91.0, quality 70.6, cash 76.7, balance sheet
74.6, valuation 55.4. Model p05/median/p95: -10.7% / +7.3% / +26.7%, P(loss) 25%. The data pack's
own flag: "Operating margin is trending down, which usually means pricing pressure or cost
inflation." Note FY2024 net income of $5.89B — the VMware acquisition year.

**Peer disagreement, the largest on the list:** net debt/EBITDA band scores 71, sector percentile
**0th**. Broadcom is the most levered name in a 16-company technology group. ROIC 14.1% is the
53rd percentile — exactly median.

From the 10-K (filed 2025-12-18): "sales to distributors accounted for 48% of our net revenue"
and top five end customers "approximately 40% of our net revenue for fiscal year 2025." And, in
the company's own framing: "We operate in a highly cyclical semiconductor industry that is
undergoing profound change due to AI."

From the news brief: AI semiconductor revenue $16.7B in Q3 FY2026 (+221% YoY); roughly 70% share
of custom AI-accelerator design services on trade-press estimates; **Marvell won a Google
custom-chip deal reported 2026-08-19, taking 5% off the stock that day**; deepening EU antitrust
scrutiny of VMware licensing (2026-09-11/13); Apple extended its custom-chip relationship to
2031 (~$30B, July 2026); Q4 revenue guidance below estimates on 2026-09-03.

**The mechanism of growth.** Two businesses. Semiconductors: Broadcom co-designs custom AI
accelerators (XPUs) and networking silicon with a handful of hyperscalers who want an
alternative to buying NVIDIA, plus a large legacy franchise in broadband, storage and wireless
(the Apple relationship). Infrastructure software: VMware and adjacent products, sold as
licences to enterprises with extremely high switching costs and, per the EU, extremely
aggressive repricing. The moat in the first is co-design relationships and SerDes/packaging IP;
the moat in the second is that ripping out a virtualisation layer is a multi-year project.

**What has to be true.**
1. AI semiconductor revenue approaches the ~$230B-by-2028 figure the company itself guided
   (reported 2026-09-09).
2. The operating margin trend turns positive. It is -2.35pp a year today.
3. VMware survives the EU probe without a licensing remedy.
4. No further custom-ASIC socket losses of the Marvell/Google type.

**The bear case.** Broadcom's growth pillar of 91 is substantially acquisition arithmetic — the
24.4% three-year revenue CAGR includes VMware, and FY2024's $5.89B of net income shows what the
deal cost. Strip the acquisitions and you have a business earning a median return on capital for
its sector (14.1%, 53rd percentile) with a declining operating margin, funded by $65.14B of debt
into a Fed that is hiking. The AI story rests on a custom-ASIC franchise the company will not
break out by customer — the news brief's finding is that the market is pricing this on trade
press, not disclosure — and which is demonstrably contestable, because Marvell took a Google
socket in August. Meanwhile the software half of the business is being investigated by the EU
for exactly the repricing that made it valuable. And the price: 45.7x trailing earnings, versus
NVIDIA at 28.1x with 62.1% ROIC and net cash. The forward P/E of 18.4 implies consensus earnings
roughly 2.5x trailing, which is where the whole valuation case lives; it is the most aggressive
forward estimate on this list after Micron's.

**Valuation.** The model's base case already assumes the margin *falls* (36.2% to 30.3%) and the
multiple de-rates hard (45.7x to 29.8x), and pairs that with a capped 60% starting growth rate —
and still gets only +7.3%. That is the honest read. **When the scorecard says 76.0 and the model
says +7.3%, the model is the one looking at the price, and the price is the problem.**

**Risks.** (1) A second custom-ASIC socket loss — the moat question, live since 2026-08-19.
(2) The EU forcing VMware licensing terms back, which is the software margin. (3) Leverage into
a hiking cycle; the 10-K's "A significant reduction in demand from certain customers or loss of
one or more of our significant customers" reads differently at 1.41x net debt. (4) The
consolidated cyclicality Broadcom names itself.

**What would change my mind.** Up: operating margin trend turning positive for two consecutive
years with net debt/EBITDA below 1.0x. Down: another named hyperscaler dual-sourcing an XPU
programme.

---

### 7203.T — Toyota Motor · Score 46.2 · Model median +17.1% · My rank 8 · **CONTESTED**

**The judgement, first.** Both numbers are wrong, in opposite directions, and the truth is
duller than either. The scorecard's D is substantially an artifact of running a manufacturer
with a captive bank through industrial bands. The model's +17.1% assumes Toyota's revenue
growth *accelerates* to 11.6% by 2031, which is not a number anyone should accept. What is
actually here is a cheap, low-return industrial whose earnings are falling, paying a safe 3.3%
dividend, whose five-year case is a re-rating bet rather than an earnings bet. That is worth
something. It is not worth 17% a year.

**Which number is measuring the thing that matters: neither, but the scorecard is closer on the
business and the model is closer on the price.** Here is the split.

**Evidence.** Price ¥3,025, market cap ¥35.82T, **-24.4% off the 52-week high** — the second
largest drawdown here. Analyst target ¥3,698.63 (19 analysts). FY Mar-2026: revenue ¥50.68T
(+5.5%), **operating income ¥3.77T — down from ¥4.80T (FY2025) and ¥5.35T (FY2024)** — net income
¥3.85T, down from ¥4.77T and ¥4.94T. Gross profit ¥8.46T, down from ¥9.58T on higher revenue.
Gross margin 16.7%, operating margin 7.4% (trend -0.16pp/yr), net margin 7.6%, **ROIC (est.)
3.6%**, ROE 12.4%. **Net debt ¥26.56T, 3.49x EBITDA**; total debt ¥43.21T. FCF ¥179.57B after
three consecutive negative years. Trailing P/E 8.6, forward P/E 9.3, **dividend yield 3.31% on a
27.0% payout ratio**, **beta 0.34**. Pillars: growth 54.4, **quality 27.7**, cash 21.8 (65%),
**balance sheet 40.1**, **valuation 91.1**. Model p05/median/p95: -1.3% / +17.1% / +37.7%; median
simulated exit P/E 11.2 against 8.6 today.

**No SEC filings. No Item 1A. Toyota is the only non-SEC filer among the ten and there is no
risk-factor disclosure for it in this data pack at all.**

From the news brief: US tariffs cost ¥1.4 trillion in FY2026, producing a **-1.4% North America
operating margin and Toyota's first North America loss in sixteen years**; FY2027 guidance points
to a consolidated operating margin near 5.9% and operating income near ¥3.0 trillion — *down
again*; Toyota cut its EV sales target by over 10% in August 2026 while raising its profit
forecast to ¥3.25T, citing hybrid demand and a weak yen; a ¥3 trillion non-vehicle "value chain"
profit target by 2030 announced 2026-09-07.

**Where the scorecard is wrong.** Toyota consolidates Toyota Financial Services, a captive lender
with a loan book. The ¥26.56T of net debt is overwhelmingly funding finance receivables, not the
car business, and the same receivables sit in the capital base that produces the 3.6% ROIC. This
project's own documentation states that banks and insurers break net debt, EV and EV/EBITDA; an
automaker with a captive bank is the same problem at half strength, and nothing in the scorecard
flags it. **The balance-sheet pillar of 40.1 and the ROIC of 3.6% are measuring a lending book,
not a manufacturer.** The 16.7% gross margin is an automotive cost-accounting convention, and its
0th-percentile ranking is against a five-company group containing Amazon (50.3% gross margin) and
LVMH. That comparison means nothing.

**Where the scorecard is right.** The 7.4% operating margin is real, it is trending down, and the
company's own FY2027 guidance says it goes to about 5.9%. The news brief is blunt about this:
"it is not a mislabeled cyclical dip, it is Toyota's own multi-year guidance." The quality pillar
of 27.7 is picking up something true.

**Where the model is wrong.** The simulation's median year-5 growth for Toyota is 11.6% — the
fitted fade's universal attractor, applied to a company that sold ~10 million vehicles into a
flat global market and grew revenue 5.5% last year while operating income fell 21%. The model
also assumes the multiple re-rates from 8.6x to 11.2x, which is 5.4% a year of pure re-rating
and is most of the +17.1%.

**The mechanism.** Toyota sells about ten million vehicles a year, increasingly hybrids, through
a dealer network, and finances a large share of them through its own captive lender. Customers
keep buying on reliability and resale value, and the hybrid powertrain — which Toyota has been
refining for twenty-eight years — is currently the right product for a market where EV adoption
has slowed. The moat is manufacturing discipline and scale, which is real but produces a 7.4%
operating margin, not a 40% one.

**What has to be true.**
1. The multiple re-rates from 8.6x toward 11x. **This is the whole case.**
2. FY2028 operating income recovers above ¥4T, from FY2027 guidance near ¥3.0T.
3. The ¥1.4T tariff hit does not repeat at that scale.
4. The yen does not strengthen materially. The news brief explicitly flags that nobody has
   decomposed Toyota's margin between currency tailwind and operational improvement — **so a
   five-year holder is partly making a currency call and should know it.**

**The bear case.** Operating income has fallen 30% in two years and the company guides it lower
again. Tariffs took the entire North America profit pool. The yen, which is doing much of the
work in the reported numbers, is a macro variable outside Toyota's control, and a hiking Fed with
a 5% 10-year is, mechanically, dollar-supportive — which helps, until a Japanese policy shift
does not. Hybrids are working now, but the pricing power comes from Chinese EV makers not yet
competing hard in Toyota's core markets; when they do, a 7.4% operating margin has very little
room. And the ¥3T value-chain target by 2030 is, as the news brief puts it, the company's own
admission that the core business's margin structure needs supplementing.

**Valuation.** At an unchanged 8.6x with a 3.31% yield, the return equals earnings growth plus
3.3%. FY2027 earnings are guided *down*. For a 10% annual total return you need roughly 6.7% a
year in earnings growth off a falling base — net income above ¥5.3T by 2031, which would be a new
record, ~7% above the FY2024 peak of ¥4.94T, after two down years. Possible. Not probable enough
to rank this above the four names at the top.

**Risks.** (1) Another tariff year at the ¥1.4T scale. (2) Yen appreciation removing the reported
margin. (3) Chinese EV price competition reaching Toyota's core markets. (4) **The complete
absence of a disclosed risk section, which means everything above rests on press and financial
statements.**

**What would change my mind.** Up: FY2028 operating income guidance above ¥4T with the North
America margin back positive; a large buyback. Down: a third consecutive year of declining
operating income; the yen below 130 to the dollar.

---

### MU — Micron Technology · Score 64.8 · Model median +20.5% · My rank 9 · **CONTESTED**

**The judgement, first.** I would not own it for five years, and the model's +20.5% — the
highest median in the entire 37-name universe — is the single least trustworthy number in this
run. Micron is at the acute peak of a commodity cycle, and the model has no concept of a memory
down-cycle because the panel it was fitted on has almost none in it. The scorecard is
directionally right and is right partly by accident.

**Which number is measuring the thing that matters: the scorecard, but only partly.** The
scorecard's cash pillar of 18.2, net income CAGR of -0.6% and FCF CAGR of -18.8% are picking up
the real signal — this business does not compound. But the scorecard's valuation pillar of 75.7
is *also* flattering it, because a forward P/E of 6.5 looks cheap and is cheap only if the
forward earnings are real.

**Evidence.** Price $1,015.80, market cap 1.15T, -19.1% off the high, 52-week low **$154.65** —
the stock has moved roughly 6.6x within twelve months. Analyst target $1,513.11 (45 analysts).
FY Aug-2025: revenue $37.38B, net income $8.54B, FCF $1.67B. **FY Aug-2023: revenue $15.54B —
down 49% from $30.76B — with a net loss of $5.83B and free cash flow of -$6.12B.** Gross margin
39.8%, operating margin 26.2%, net margin 22.8%, **ROIC (est.) 11.8%, FCF margin 4.5%, FCF yield
0.15%**. Net debt $4.97B. Trailing P/E 22.9, **forward P/E 6.5**, dividend yield 0.05%, beta 2.22.
Pillars: growth 66.2, quality 67.4, **cash 18.2**, balance sheet 93.4, valuation 75.7. Model
p05/median/p95: +1.2% / +20.5% / +43.1%; base-case scenario +30.0%/yr.

**Peer disagreement:** gross margin 39.8% scores 55 on the band and sits at the **7th percentile**
of its sector. FCF margin scores 35 on the band and sits at the **0th percentile**.

From Micron's own 10-K (filed 2025-10-03): "In the past five years, annual percentage changes in
DRAM average selling prices have ranged from plus low 40% to a minus high 40% range. In the past
five years, annual percentage changes in NAND average selling prices have ranged from plus low
30% to a minus low 50% range... **In some prior periods, average selling prices for our products
have been below our manufacturing costs.**" That is the company stating under legal liability
that the current windfall is a cycle position.

From the news brief: DRAM contract prices rose ~90% in Q1 2026 and 58-63% QoQ in Q2 2026; fiscal
Q3 2026 revenue reached $41.46B in a single quarter; consensus peak-timing has already slipped
once in 2026, from H1 2027 to "no earlier than Q4 2027, possibly 2028"; CXMT is taking share at
the trailing edge; price-fixing class actions were filed June-July 2026; roughly $250bn of
committed US capacity through 2035, with nobody able to say whether it lands into the up-cycle or
the down-cycle.

**Why the model's number is wrong, specifically.** Two compounding problems.

First, the margin vintage. Micron's TTM net margin implied by its own reported multiples is about
**55.4%** (P/S 12.71 ÷ trailing P/E 22.94). Its best annual net margin *ever* before this cycle
was 28.2% in FY2022. The model projects forward from the FY2025 annual margin of 22.8% and drifts
it *up* to 28.8%, while pricing the entry off a multiple built on 55% TTM margins. The resulting
effective sales multiple is 5.23 against a reported 12.71 — the entry is being priced at 41% of
the real level. This single inconsistency is worth roughly half the projected return.

Second, the fade. The model's base case implies earnings multiply about 3.9x over five years
(revenue index 3.10 times a margin rising from 22.8% to 28.8%) while the multiple contracts 5%.
Micron earning 3.9x its current TTM would put its net income near NVIDIA's today — out of a
commodity memory business. The fitted fade cannot produce a down-cycle at the median: its
attractor is +11.3% a year, and Micron has had a -49% revenue year within the last three.

**Run it honestly.** Start from the actual TTM margin, let it revert toward a good-but-not-peak
22.8%, value it on a mid-cycle 12-18x rather than 18.4x, and price the entry off the reported
12.71 sales multiple. **The same arithmetic then produces somewhere between -8% and 0% a year.**
That is a scenario on stated assumptions, exactly like the model's, and I think the assumptions
are better.

**The mechanism.** Micron sells DRAM and NAND — commodities where the product is fungible between
three suppliers and the price is set by the marginal bit of supply. The only durable variation is
HBM, where packaging complexity and qualification cycles create genuine switching friction and
contracted pricing. If HBM becomes a majority of the business and stays contracted, Micron is a
different company. That is the bull case and it is not crazy.

**What has to be true.** (1) DRAM contract prices do not fall more than 20% in any of the next
five years, against a company-disclosed historical range of -high 40%. (2) HBM becomes structurally
contracted rather than spot-priced. (3) The ~$250bn US buildout lands into demand. (4) CXMT stays
at the trailing edge.

**The bull case, stated fairly.** The supply side is more disciplined than in past cycles —
Samsung, SK Hynix and Micron are all reported to be resisting overbuild — and HBM demand is
contracted a year ahead. If that holds, memory has genuinely re-rated from a commodity to a
semi-contracted component business, and a 1.15T market cap is defensible. I do not believe it,
but the argument is real and it is the reason the stock is where it is.

**The bear case.** Micron's own 10-K has already written it. ASPs swing ±40-50% a year and have
been below manufacturing cost within living memory. Three years ago this company lost $5.83B and
burned $6.12B of cash on a 49% revenue decline. Nothing about the physics of DRAM has changed;
what has changed is one demand source. Every previous memory cycle also had one. If mid-cycle net
income settles at, say, $20B — more than double the FY2025 peak, generously allowing for a
permanently larger HBM business — then at 12x mid-cycle Micron is worth about $240B, 79% below
today. That is not a prediction; it is the arithmetic of what mean reversion would mean here.

**Risks.** (1) The cycle, which is the whole thing. (2) The capacity commitment landing into a
downturn — the 10-K's own "We may not be able to achieve expected returns from capacity
expansions." (3) CXMT reaching the leading edge faster than expected. (4) An adverse price-fixing
outcome.

**What would change my mind.** Up: HBM shifting to multi-year contracted pricing covering a
majority of revenue, disclosed. Down: any quarter of sequential DRAM ASP decline.

---

### ARM — Arm Holdings · Score 66.4 · Model median -16.5% · My rank 10 · **CONTESTED**

**The judgement, first.** Do not own. This is the clearest call on the list and the only one
where I think the scorecard is not merely incomplete but actively misleading. The model is
measuring the thing that will decide the five years and the scorecard is not.

**Which number is measuring the thing that matters: the model, decisively.** And the *way* it
gets there matters. The model clamps the exit P/E at 60 in all three scenarios and its median
simulated exit multiple is 69.9, near the 70 ceiling — and it still produces -18.1% base and
-16.5% median with 99% of paths losing money. **The model is not forecasting a de-rating. It is
observing that even at an exit multiple nobody would pay, the arithmetic does not close.**

**Evidence.** Price $275.61, market cap $294.35B, **-39.1% off the 52-week high** — the largest
drawdown of the ten. Analyst target $288.70 (40 analysts, "buy") — **about 5% above the current
price, the only one of the ten where the sell side is effectively at the money.** FY Mar-2026:
revenue **$4.92B**, operating income $908M, net income **$904M**, FCF $949M, R&D $2.78B.
**Trailing P/E 278.4, forward P/E 90.2, price/sales 57.1, EV/EBITDA 273.5.** Gross margin 97.5%,
operating margin 18.5% **with a trend of -0.34pp/yr**, net margin 18.4%, **ROIC (est.) 8.7%, ROE
13.4%**, R&D intensity 56.4%. Net cash $3.14B. No dividend. **Beta 3.89** — by far the highest
here. Pillars: growth 81.8, quality 58.5, cash 57.4, **balance sheet 99.0**, **valuation 25.1**.
The data pack's own flag: "A forward P/E of 90 prices in years of execution, leaving little
margin for a stumble."

**Peer disagreements:** FCF margin band 74 vs sector 20th percentile (+54); operating margin band
61 vs 33rd; ROE band 48 vs 20th. Its 97.5% gross margin at the 100th percentile is a structural
artifact of IP licensing, not a moat. **ROIC 8.7% is the 27th percentile of its sector.**

From the 20-F (filed 2026-05-26), Arm's own words: "our top five customers (including Arm China
and SoftBank Group) collectively accounted for approximately 57%, 56% and 54% of our total
revenue" for FY2026/25/24, "and our largest customer individually, Arm China, accounted for
approximately 16%, 17% and 21%." And: "**Neither we nor SoftBank Group control the operations of
Arm China.**" And, prophetically: "Customers may decide to license our architecture and develop
their own processors based on our architecture, rather than utilize our processor products."

From the news brief: Arm launched its own AGI CPU for data centres on 2026-03-25, framed by the
company as a "significant shift" — **putting it in direct competition with its own licensees**.
The FTC opened an antitrust probe in May 2026 into whether this lets Arm degrade licensing terms
for customers now competing with it; unresolved as of 2026-09-20. An active dispute with
Qualcomm continues.

**Why the scorecard fails here.** ARM scores 66.4 — above Amazon and Toyota — because the balance
sheet pillar is 99.0 (net cash, no debt, which is true and irrelevant) and growth is 81.8. The
valuation pillar of 25.1 carries 15% weight, so the composite cannot express "this price is
impossible." **This is a structural limit of the fixed yardstick, not a mistake in this run, and
it is exactly the case the project's own documentation anticipates: a rules-based score cannot
see a business changing shape, and Arm changed shape in March 2026.**

**The mechanism.** Arm licenses CPU instruction-set architecture and core designs, collecting an
up-front licence fee and then a royalty on every chip shipped containing its IP — roughly a
low-single-digit percentage of chip value across essentially every smartphone on earth and a
growing share of data-centre CPUs. Customers keep paying because the entire software ecosystem
compiles to Arm. That is a genuinely excellent business model. It generated $4.92B of revenue and
$904M of net income last year.

**What has to be true, for the price merely to hold.** Revenue up roughly 5-8x by 2031 and the
net margin roughly doubling, at an exit multiple above 40x. Against: a three-year revenue CAGR of
22.5% and an operating margin trending *down*.

**The arithmetic.** Take Arm's own 22.5% three-year revenue CAGR, hold it for five years:
$4.92B becomes $13.6B in FY2031. Apply today's 18.4% net margin: $2.50B of net income. Exit at
40x — a multiple almost no mature company sustains: **$100B, versus $294.35B today. A 66% loss,
about -19.5% a year.** My arithmetic and the model's -16.5% agree from different directions. To
merely break even you need revenue near $40B at today's margin, or $25B at a 30% net margin the
company has never earned.

**The bull case, stated as strongly as I can.** Arm is capturing silicon value it previously left
to licensees. If the AGI CPU line takes real data-centre share — a market where Arm's power
efficiency is a genuine advantage and where hyperscalers are already designing their own
Arm-based server CPUs — then revenue is not growing 22.5%, it is inflecting, and the net margin
goes to 30%+ because silicon carries its own gross margin on top of royalties. Get to $25B of
revenue at a 30% margin by 2031 and 40x gets you back to today's price. **The news brief's
finding is that nobody has published the split between legacy licensing growth and AGI CPU growth
— so this case cannot be checked from here.** That is the honest state of the evidence, and it
does not rescue a 278x trailing multiple.

**The bear case.** Nothing has to go wrong. The arithmetic already fails. And things are in fact
going wrong: an FTC probe into the exact strategic move the bull case depends on; a direct
conflict with the licensees who are 57% of revenue; a largest customer (Arm China, 16%) that Arm
does not control; a Qualcomm dispute; and a beta of 3.89 into a 5% 10-year Treasury, which makes
this the most duration-exposed name of the ten by a wide margin.

**Risks.** (1) The price. (2) The FTC probe going against the AGI CPU strategy. (3) Licensee
defection — the 20-F names it: customers developing their own processors on Arm's architecture.
(4) Arm China, a 16% customer Arm does not control. **All four are unpriced; a stock at 278x
trailing prices none of them.**

**What would change my mind.** Up: an AGI CPU design win at a named hyperscaler with disclosed
volume, plus the FTC closing without action, plus the stock 50% lower. Down: nothing needed.

---

## 7. The four disagreements, settled plainly

The brief asks which of the two numbers is measuring the thing that will matter over five years.
Here are the four answers in one place.

**ARM (score 66.4, model -16.5%): the model, decisively.** The scorecard's composite cannot
express an impossible price because valuation carries 15% weight and the balance-sheet pillar
scores 99.0 for having no debt. The model reaches its answer by clamping the exit multiple at 60
and finding that the arithmetic still fails — which is not a forecast of a de-rating but an
observation about the price. My own independent arithmetic (-19.5% a year on Arm's own 22.5%
revenue CAGR and today's margin, exiting at 40x) agrees. **Trust the model.**

**MU (score 64.8, model +20.5%): the scorecard, and it is right partly by accident.** The
scorecard's cash pillar of 18.2, net income CAGR of -0.6% and FCF CAGR of -18.8% correctly detect
a business that does not compound. But its valuation pillar of 75.7 rewards a forward P/E of 6.5
that is only cheap if the forward earnings are real. The model is wrong for two identifiable
reasons: it prices the entry off a peak-earnings multiple while projecting from a stale annual
margin (effective sales multiple 5.23 against a reported 12.71), and its fitted fade has an
attractor of +11.3% a year and cannot produce the down-cycle that Micron's own 10-K says has
happened repeatedly. **Trust neither number; trust the 10-K.**

**AMZN (score 57.2, model +18.1%): the model on direction, the scorecard on magnitude.** The C
grade is a capex artifact — a company spending $220B a year cannot score well on a cash pillar
built from free cash flow. The model correctly sees that reported FCF understates earnings power.
But it prices the entry at a 2.20 sales multiple against a reported 3.53, because Amazon's TTM
earnings are inflated by non-operating investment gains. **Correct that and the same arithmetic
gives about 9.5% a year, which is my number.** Worth owning; not worth 18%.

**7203.T (score 46.2, model +17.1%): neither, and the failure modes are opposite.** The
scorecard's D is largely captive-finance distortion — ¥26.56T of net debt funding a loan book,
and a 3.6% ROIC computed against a capital base containing finance receivables — plus a gross
margin compared against Amazon and LVMH. The model's +17.1% assumes revenue growth accelerating
to 11.6% and a 30% multiple re-rating, for a company whose operating income has fallen 30% in two
years and is guided lower again. **The honest answer is a cheap, low-return industrial with a
safe 3.3% dividend whose case is a re-rating bet, and neither tool is built to say that.**

---

## 8. Portfolio note: what these ten have in common

Say it plainly: **six of these ten are one position wearing six names.** NVDA, TSM, AVGO, ASML,
MU and ARM all sell into the same capital-spending decision, taken by the same dozen buyers, at
four points of one supply chain. They do not diversify each other. A single hyperscaler guiding
2027 capex flat would reprice all six in the same session.

META and AMZN sit on the other side of that trade — the capex is their cost, not their revenue —
which is a real hedge on cash flow and only a partial one on price, because both would still
de-rate with the sector. LLY and 7203.T are genuinely outside it.

The practical implication, which is portfolio construction rather than stock selection and which
I flag rather than prescribe: an equal-weight position in all ten puts roughly 60% of capital in
one capital-spending cycle. If the concentration is to be reduced without leaving the theme, the
efficient move is to own fewer of the six sellers rather than to add a seventh.

Three watch items, in priority order, that would tell a holder the cycle is turning **before** the
earnings do:

1. **Hyperscaler capex guidance on the Q4 2026 and Q1 2027 calls.** Not semiconductor bookings.
   The grid bottleneck — four-year interconnection queues, Gartner's 40%-power-constrained-by-2027
   forecast — decouples chips shipped from chips earning a return, so bookings will lag.
2. **Credit spreads on AI-linked debt.** The macro brief identifies the claim that the AI
   financing circle "just hit its first stress test" from the September rate hike as fresh
   framing, not yet digested. NVIDIA disclosed over $540bn of financing arrangements in 2026. If
   that shows up in financing costs rather than staying theoretical, it is new information.
3. **Meta's and Amazon's free cash flow.** They are the buyers. When their FCF recovers, the
   buildout has a top — which is simultaneously good for them and the first sign of trouble for
   the six sellers.

---

## 9. Sources and snapshot dates

| Source | Date | What it supplied |
|---|---|---|
| `data/reports/2026-09-20-full-universe-datapack.md` | 2026-09-20 15:34 | Scorecards, pillars, scenarios, metrics, reported history, filings, risk factors |
| `data/reports/2026-09-20-macro-brief.md` | 2026-09-20 | Fed 3.75-4.00% (2026-09-16), 10-yr 5.00-5.04%, CPI 3.4%, hyperscaler capex and FCF projections, export-control regime, MFN drug pricing, 17-of-37 concentration count |
| `data/reports/2026-09-20-watchlist-news-brief.md` | 2026-09-20 15:43 | 1,632 articles triaged across the ten; company-disclosed concentration figures; Arm AGI CPU and FTC probe; Toyota tariff arithmetic; ASML China DUV; Micron ASP history |
| `data/reports/2026-09-20-full-universe-prediction.md` | 2026-09-20 15:32 | Simulation medians and ranges, fitted fade (R²=0.030, n=76) |
| `data/raw/<TICKER>/2026-09-20.json` | 2026-09-20 08:30-08:32 UTC | Prices, market caps, multiples, currency-mismatch flags |
| `data/predictions/<TICKER>/2026-09-20.json` | 2026-09-20 | Simulation inputs, ending-state medians, sensitivity |
| `data/scores/<TICKER>/2026-09-20.json` | 2026-09-20 (re-run for this report) | Pillar scores and coverage |
| `tools/peers.py <TICKER>` | run 2026-09-20 | Sector percentiles and band/peer disagreements |
| SEC EDGAR via `data/filings/` | filings dated 2025-10-03 to 2026-09-18 | Item 1A language quoted above |

Market data is Yahoo Finance: delayed, revised, and adequate for structural comparison over
years but not for anything time-sensitive. `roic_est` uses a flat 21% tax haircut, so it ranks
rather than measures. News tagging is keyword matching and mislabels articles routinely; the
news brief re-read the underlying items rather than trusting the tags.

**Known gaps in this report, stated rather than hidden:** no Item 1A for Toyota (non-SEC filer),
none parsed for ASML, none collected for Amazon, and only three factors captured for TSM. The
implied TTM net income figures used in the valuation sections are inferred from market cap and
reported multiples, not read off a statement, because the data pack carries annual history only.
Meta's sector percentiles are unusable (3 companies) and are not quoted. Whether GLP-1 volume
expansion offsets the MFN price cut is not resolvable from anything available here, and I have
not pretended to resolve it.

---

*This is research tooling, not investment advice. Nothing above is a recommendation to buy,
sell or hold any security. Every projected return in this report is arithmetic on stated
assumptions, not a forecast: the model has never been validated out of sample, it cannot be with
this data source, and its fitted fade explains 3% of the variation in the panel it was estimated
on. The assumptions are the argument. All decisions and all risk belong to the reader.*
