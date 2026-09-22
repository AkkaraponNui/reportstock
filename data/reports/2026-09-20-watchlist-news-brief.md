# Watchlist News Brief — 10 tickers, as of 2026-09-20

Scope: NVDA, TSM, META, AVGO, LLY, ARM, MU, ASML, 7203.T (Toyota), AMZN. Collected via
`tools/fetch_news.py <TICKER> --days 180` (180-day window, 8-angle query, deduped) on
2026-09-20, cross-checked against each company's own SEC risk-factor disclosure
(`tools/fetch_filings.py <TICKER> --risk-factors`) and verified against the open web where
the collected feed was ambiguous or thin. TSM and 7203.T are non-US issuers; TSM files a
20-F, Toyota files 6-Ks and has no comparable EDGAR risk-factor narrative, so that ticker's
disclosed-risk section leans on TSM/ARM-style 20-F peers and press reporting instead.

**Headline across all ten: nothing in the last 180 days rewrites a five-year thesis outright.
The real structural news is concentration — of customers, of revenue in one drug franchise,
of a chip designer's own top buyer — not new competition or a new regulatory regime.** Two
items are genuine regime-change candidates worth weighing seriously: Arm's move from IP
licensor to silicon competitor (with an open FTC probe attached), and China's first
credible domestic DUV lithography tool (still four generations behind ASML). Everything
else is either a cyclical swing already visible in the numbers (the memory upcycle, Toyota's
tariff-driven margin compression) or noise — and noise is the overwhelming majority of the
raw feed for every name on this list.

---

## NVDA — customer concentration is real and getting worse, not better

**Structural — customer concentration.** NVIDIA's own FY2026 10-K (filed 2026-02-25) states:
"For fiscal year 2026, sales to one direct customer represented 22% of total revenue and
sales to another direct customer represented 14% of total revenue, all of which were
primarily attributable to the Compute & Networking segment." Third-party aggregation of the
Q3 FY2026 10-Q (reported via Motley Fool/BigGo, not independently re-verified against the raw
filing here) puts four customers at a combined 61% of that quarter's $57B in revenue, up from
prior quarters — a rising, not falling, concentration trend. This is the single most
important fact for a five-year holder: NVDA's $216B run rate depends on continued capex
decisions by a handful of hyperscalers and AI labs, and the company says so under legal
liability. Confidence: high — the number comes from NVIDIA's own filing, not a headline.
What would confirm/kill it: the FY2027 10-K's customer table, and whether the two largest
names (widely reported to include Microsoft and possibly a SpaceX-linked entity per
guidance commentary) diversify or concentrate further.
Source: [NVIDIA FY2026 10-K risk factors, data/filings/NVDA/2026-09-20.json, filed 2026-02-25]; [Q3 concentration figures via BigGo Finance, "Nvidia's Revenue 44% Concentrated in 3 Customers," 2026](https://finance.biggo.com/news/2abfd8af-8b6b-4583-bbe4-7cc44f0af0e4); [Motley Fool, "Blackwell Sales Are Off the Charts... and Worryingly, so Is Its Customer Concentration," 2025](https://www.fool.com/investing/2025/11/27/blackwell-off-charts-nvidia-customer-concentration/).

**Structural — effectively zero China revenue.** CEO Jensen Huang stated in early May 2026
that NVIDIA now has "zero percent" market share in China's AI chip market, and separately
that Chinese chipmakers' domestic share of the local AI GPU market rose to roughly half by
April 2026 (from a lower base), with local players delivering 1.65 million AI GPUs as
Chinese data centers are directed to domestic chips. This is a structural loss of a market
that was material a few years ago, now priced as effectively gone — worth noting as a floor
already reached rather than a risk still unfolding. Confidence: high (direct CEO statement,
widely reported). Source: [Yahoo Finance/tomshardware, "Jensen says Nvidia now has 'zero
percent' market share in China," 2026-05-03/04](https://www.tomshardware.com); [Reuters,
"Chinese chipmakers claim nearly half of local market as Nvidia's lead shrinks,"
2026-04-01].

**Structural (watch, not yet resolved) — DOJ antitrust probe of the Groq licensing deal.**
The DOJ opened an investigation (reported publicly 2026-09-09/10 by NYT/Bloomberg/Axios,
though the probe itself reportedly began in December 2025) into whether NVIDIA structured
its ~$17-20B non-exclusive licensing deal with AI-chip startup Groq to avoid formal
antitrust merger review. If regulators find the structure improper, it could constrain how
NVIDIA does future "acqui-hire via licensing" deals — a pattern it has used repeatedly
(Groq, Hugging Face at $12.9B in September 2026, SchedMD, Kumo AI). This is preliminary and
unresolved; confidence is low that it changes five-year earnings power, but it is worth
tracking because it targets the deal-making mechanism NVIDIA increasingly relies on to
extend its platform rather than just a single transaction.
Source: [Axios, "DOJ investigates Nvidia's deal with Groq," 2026-09-10](https://www.axios.com/2026/09/10/doj-nvidia-groq-antitrust); [Bloomberg, "DOJ Probes Nvidia's $20 Billion License Deal With Groq on Antitrust Concerns," 2026-09-10](https://www.bloomberg.com/news/articles/2026-09-10/doj-probes-nvidia-s-license-deal-with-groq-on-antitrust-concerns).

**Cyclical.** The 70% FY2028 revenue growth guide (given 2026-08-26/28) is still the
company's own number — deceleration from the prior ~100% CAGR is guided, not discovered,
and the market's "circular financing" bubble worry (Bank of England, various analysts) is a
sentiment debate, not a disclosed fact change. The paused revenue-sharing deals with AI
cloud firms "over antitrust fears" (2026-08-27/28) look procedural rather than a demand
signal. Supply/capacity commentary ("$279B supply-chain gamble," Palantir/Nemotron
partnership) is operational plumbing, not a moat change.

**Disclosed risk (company's own language, 10-K).** Beyond the concentration paragraph
quoted above, NVIDIA's risk factors also flag: "Over the past three years, we have been
subject to a series of shifting and expanding export control restrictions, impacting our
ability to serve customers outside the United States" — boilerplate in form but, given the
China market-share data above, not boilerplate in substance for this company specifically.

**Open question.** No article in the 90-180 day window quantifies whether NVDA's non-US,
non-China revenue growth rate is itself decelerating faster than the blended 70% guide
implies. The 10-Q customer tables would settle it; that data exists but wasn't independently
re-pulled here beyond the FY2026 10-K figures already quoted.

---

## TSM — geopolitical exposure: nothing materially changed in twelve months; watch the diversification instead

**What changed, factually: not much on the geopolitical axis itself.** No article in the
180-day window, nor the wider web search, shows an actual escalation (blockade, new
sweeping export ban, military incident) affecting TSMC operations in the last year. What
changed is TSMC's own hedge against that risk: it lifted its Arizona commitment repeatedly
through 2026, reaching roughly $265-300B in cumulative US investment by autumn 2026 (up from
$165B pledged in 2025), added a 10-year Amkor advanced-packaging partnership in Arizona, and
hit "a milestone" in its Germany joint venture (2026-09-15). Capacity, not geography, is now
the binding constraint: TSMC said in September 2026 it is "unable to keep pace with the AI
boom despite fivefold expansion." Confidence: high on the facts (no incident; large,
continuing US/Japan/Germany capex), moderate on interpretation (geographic diversification
reduces but does not eliminate the Taiwan concentration, since leading-edge capacity remains
overwhelmingly in Taiwan for years yet).
Source: [Reuters/CNBC/WSJ, TSMC Arizona expansion coverage, throughout Jul-Sep 2026, e.g. "TSMC to Invest a Further $100 Billion in U.S.," WSJ, 2026-07-17]; [Taipei Times, "TSMC's Germany venture hits milestone," 2026-09-15]; [TradingKey, "TSMC Reported $35.9B Revenue. Why Is Demand Still Outpacing Supply?," 2026-09-19].

**Structural (separate from the Taiwan-China question) — Taiwan is tightening its own
export rules,** not loosening them, adding 279 entities to its strategic-goods watch list
and weighing criminal penalties for unauthorized AI-chip shipments. This is a second,
distinct channel of geopolitical risk (Taipei restricting outbound tech, independent of
Washington or Beijing) that the "China invasion" framing usually misses.
Source: [ec-compliance.com, "Taiwan strengthens export controls on strategic high-tech goods," 2026].

**Cyclical.** Revenue growth remains extraordinary (August monthly revenue +53% YoY; June
+68%) and margin scored "in focus" at 67.7% given the capex ramp (2026-09-01) — this is
demand-cycle strength, not a moat change, and a downturn in AI capex would compress margins
before it compresses the geopolitical thesis.

**Open question.** The one genuinely tail-risk scenario analysts flag for 2026-2027 — a
Chinese "quarantine" or shipping/insurance disruption around Taiwan short of open conflict —
has no evidence of having moved closer or further away in the news collected. Its absence
from the 180-day feed is itself informative: it means the market has not had to price a
live event, only a standing possibility. A source that would settle direction: Taiwan
Ministry of National Defense assessments or U.S. DoD China Military Power reports, neither
of which is in this news feed.

---

## META — the capex is producing a return by the company's own accounting, but free cash flow says the market isn't fully convinced

**What changed.** Meta raised 2026 capex guidance twice — to $125-145B (April 2026 Q1 call)
and again to $130-145B (July 2026 Q2 call) — while free cash flow fell sharply, reported at
$784M for Q2 2026 (down from much higher prior-year levels), which the company itself
foreshadowed by warning about "what to sell vs. what to keep" in AI compute allocation.
Separately, Meta states (per its own reporting) that incremental ROIC on recent AI
investment remains above 20% and cash-based ROIC above 52% — a company-provided metric,
not yet independently audited by a third party in the sources reviewed. Confidence: medium.
The ROIC figure is Meta's own framing and could reflect legacy ad-business cash flows being
attributed to AI rather than AI-specific payback; the FCF collapse is a hard, reported
number. What would confirm/kill it: FCF trajectory over the next 2-3 quarters — if it
recovers as the buildout plateaus, the ROIC framing holds; if it stays negative/near-zero
through 2027, the "bet still outstanding" read is correct.
Source: [Yahoo Finance/Investing.com, "Meta Platforms: From Heavy AI CapEx to 2026 ROI?," 2026](https://www.investing.com/analysis/meta-platforms-from-heavy-ai-capex-to-2026-roi-200673593); [24/7 Wall St., "Meta Platforms Falls 4% on Trial Risk With Costs Up 55%, Free Cash Flow Down to $784M," 2026-08-18]; [CNBC, "Meta's stock drops on disappointing guidance, dwindling free cash flow," 2026-07-29].

**Structural, but a one-time cost, not a moat change — $17-18B child-safety settlement**
(agreed 2026-08-26) with a coalition of state attorneys general over alleged addictive
design in Facebook/Instagram for minors, requiring platform changes. This is real money and
a real behavioral-design constraint going forward, but it is a settled, bounded liability,
not an ongoing structural drag — unless it becomes the template for a second wave of state
suits (thousands of similar suits were allowed to proceed per an August 2026 appeals
ruling). Note on duplication: this single settlement generated roughly a dozen separate
state-AG press releases plus national wire coverage in the dataset — one fact, not twelve.
Source: [BBC, "Meta to pay up to $18bn to settle claims its platforms harm children,"
2026-08-26]; [Reuters, "US court rules Meta, other tech firms must face thousands of
lawsuits over social media addiction," 2026-08-11].

**Cyclical/noise-adjacent.** The Muse AI agent launch (2026-09-09) moved the stock but has
no disclosed revenue attached yet — too early to score as structural. China blocking Meta's
$2B Manus acquisition (April 2026, later unwound) removed a small bolt-on, not a strategic
pillar.

**Open question.** No article quantifies what fraction of the 2026 capex is fungible
(reusable compute) versus AI-specific depreciating hardware — the actual determinant of
whether this is "a return being earned" or "a bet outstanding." That would need to come from
the 10-K's capex/depreciation footnotes, not the press.

---

## AVGO — the AI growth is customer-concentrated, but AI is not yet all of Broadcom

**Structural.** Broadcom's own FY2025 10-K (filed 2025-12-18) states: "sales to distributors
accounted for 48% of our net revenue" and "aggregate sales... to our top five end customers
accounted for approximately 40% of our net revenue for fiscal year 2025." Within the AI
segment specifically, third-party industry reporting puts Broadcom's share of the custom
AI-accelerator design-services market at roughly 70%, with confirmed XPU customers Google,
Meta, OpenAI, Anthropic, Apple, ByteDance and Fujitsu — AI semiconductor revenue hit $16.7B
in Q3 FY2026 (+221% YoY). So: the *AI* growth line is genuinely concentrated in a handful of
hyperscalers (Google and Meta most prominently, per multiple reports), but total-company
revenue also includes VMware software, networking and broadband, which dilutes that
concentration at the consolidated level. Confidence: high on the 10-K figures (company's own
disclosure); medium on the AI-specific customer split, which comes from trade press
estimates, not a Broadcom-published breakdown — the company does not disclose per-customer
AI revenue.
Source: [Broadcom FY2025 10-K risk factors, data/filings/AVGO/2026-09-20.json]; [Next Platform, "Broadcom Rides Rocketing Trend For Custom AI Accelerators," 2026-09-10]; [TechTimes, "Broadcom Custom AI Chip Revenue Surges 221% to $16.7B," 2026-09-03].

**Structural — a competitive crack in the assumed AVGO/duopoly.** Marvell won a Google
custom-chip deal reported 2026-08-19, contributing to a 5% AVGO share drop that day. This is
the first concrete sign that Broadcom's AI-ASIC dominance is not exclusive even with its
largest reported customer.
Source: [24/7 Wall St., "Broadcom Falls 5% as Marvell Lands Google Custom Chip Deal, VMware and Financing Concerns Persist," 2026-08-19].

**Cyclical/regulatory, not yet resolved.** EU antitrust scrutiny of VMware licensing changes
deepened through September 2026 (fresh EU probe reported 2026-09-11/13) — ongoing, outcome
unknown. Apple extended its custom-chip relationship with Broadcom through 2031 (~$30B,
July 2026) — a structural positive for the non-AI side of the business, offsetting some of
the AI-customer concentration risk.

**Open question.** No source — including Broadcom's own disclosures — breaks out AI revenue
by individual named customer. That opacity is itself the finding: the market is pricing
Broadcom's AI growth on trade-press estimates of customer mix, not company-verified figures.

---

## LLY — GLP-1 concentration is the risk that matters; competition and pricing are secondary

**Structural — extreme product concentration, disclosed by the company.** Eli Lilly's own
FY2025 10-K (filed 2026-02-12) states: Mounjaro and Zepbound "accounted for 56 percent of
our total revenues in 2025," and six products together (including Mounjaro, Zepbound,
Verzenio, Trulicity, Taltz, Jardiance) accounted for 82%. This is the central five-year risk:
more than half of Lilly's revenue sits in a two-drug GLP-1 franchise exposed to patent
cliffs, pricing policy, and — new in 2026 — cannibalization from Lilly's own oral pill.
Confidence: high (direct 10-K quote).
Source: [Eli Lilly FY2025 10-K risk factors, data/filings/LLY/2026-09-20.json, filed 2026-02-12].

**Structural, still unfolding — Foundayo (Lilly's own oral GLP-1) is capturing share from
Lilly's injectables, not just from Novo Nordisk.** Reuters reported 2026-09-14 that Foundayo
"has captured over 30% of new US patients on oral weight-loss drugs." Whether this expands
Lilly's total addressable obesity market (a structural positive — orals reach patients who
won't inject) or simply cannibalizes higher-margin injectable revenue (margin-negative) is
not yet resolved in the reporting; an analyst downgrade the same week cited "obesity market
overestimation concerns," which retail dismissed but which is at least a live debate, not
settled. Confidence: medium — the 30%+ figure is reported, but its margin implication is not.
Source: [Reuters via Yahoo Finance, "Lilly says Foundayo has captured over 30% of new US patients on oral weight-loss drugs," 2026-09-14]; [Stocktwits, "LLY Shares Dive On Analyst Downgrade Citing Obesity Market Overestimation Concerns," 2026-09-17].

**Structural, smaller — losing share to generics outside the US.** Lilly is losing GLP-1
market share in India specifically as generic weight-loss drugs flood that market
(2026-04-10) — a reminder that IP protection for these molecules is uneven across
Lilly's global footprint, unlike its US/EU core.
Source: [CNBC/qz.com, "Eli Lilly market share drops, Novo Nordisk holds firm as generic weight-loss drugs flood India," 2026-04-10].

**Cyclical/legal.** The Novo Nordisk lawsuit over allegedly misleading GLP-1 advertising
(filed 2026-07-21) and Lilly's own black-market/counterfeit-retatrutide lawsuits (August
2026) are litigation noise around a genuinely large and growing category, not a change to
the category's size. The ~$25B, roughly ten-deal acquisition spree through 2026 (AtaiBeckley,
Merida, Centessa, Kelonia, Ajax Therapeutics, three vaccine-related deals) is real capital
deployment toward diversifying beyond GLP-1, but too early and too small individually to
offset the 56% concentration figure above; it is the right defensive move, not yet a
structural offset.

**Disclosed risk, company's own language.** "We derive a significant percentage of our
total revenue from relatively few products and sell our products through consolidated
supply chain entities, which subjects us to various risks" — this is not boilerplate for
Lilly; it is the single most decision-relevant sentence in the filing given the 56%/82%
figures that follow it.

**Open question.** No source in the collected window quantifies Foundayo's gross margin
relative to Zepbound's, which is the number that would resolve whether the oral pill's share
gains help or hurt five-year earnings power.

---

## ARM — the scorecard and the model disagree because Arm just changed what kind of company it is

**Structural — Arm stopped being a pure IP licensor in March 2026.** Arm launched its own
AGI CPU for data centers (announced 2026-03-25, framed by the company as a "significant
shift"), putting it in direct competition with some of its own chip-licensee customers for
the first time. This is the event that explains both sides of the disagreement: it is why
growth expectations are high (Arm is capturing silicon value it previously left to
licensees) and why the model's return estimate is hostile (Arm now carries execution and
customer-alienation risk on top of an already extreme valuation).

**Structural — this triggered a live FTC antitrust probe, unresolved as of 2026-09-20.**
Reported 2026-05-15/17, the FTC is investigating whether Arm's new position lets it
"illegally monopolize parts of the semiconductor market" by degrading licensing terms for
CPU-design customers now competing against Arm's own chip. As of the most recent reporting
found (late July/August 2026), no resolution has been announced. Separately, Arm is already
in an active legal dispute with Qualcomm over related licensing conduct.
Source: [Bloomberg, "Arm Holdings said to face US antitrust probe over chip tech," 2026-05-15](https://www.bloomberg.com/news/articles/2026-05-15/arm-holdings-said-to-face-us-antitrust-probe-over-chip-tech); [Yahoo Finance, "US FTC reportedly launches antitrust probe into Arm following its launch of its own AGI CPU," 2026-05](https://finance.yahoo.com/sectors/technology/articles/us-ftc-reportedly-launches-antitrust-114000067.html).

**Structural — customer concentration is company-disclosed and material.** Arm's 20-F
(filed 2026-05-26) states: "our top five customers (including Arm China and SoftBank Group)
collectively accounted for approximately 57%, 56% and 54% of our total revenue for the
fiscal years ended March 31, 2026, 2025 and 2024, respectively, and our largest customer
individually, Arm China, accounted for approximately 16%, 17% and 21% of our total revenue,
respectively, during those fiscal years." Arm China's percentage of revenue is declining,
but it remains a large single-customer exposure, and Arm China's governance/control has
historically been flagged separately as a distinct risk (Arm Holdings plc does not fully
control the Arm China joint venture). This is the concentration the scorecard's growth score
does not see.
Source: [Arm Holdings FY2026 20-F risk factors, data/filings/ARM/2026-09-20.json, filed 2026-05-26].

**Cyclical/valuation.** Supply constraints reportedly capping near-term revenue despite
"roaring demand" (WSJ, 2026-05-06) is a near-term ceiling, not a structural one. Repeated
valuation commentary (P/B ~35.7x, August 2026) is exactly what the model's -16.5%/year
median is reacting to — the news confirms the valuation is stretched; it does not resolve
whether growth can outrun it.

**Open question.** No source quantifies how much of Arm's forward revenue growth is
projected to come from the new AGI CPU line versus the legacy licensing business — that
split would show whether the FTC risk is concentrated in a small, separable part of the
business or in the growth engine itself.

---

## MU — squarely in the acute up-leg of a cycle the company itself says swings ±40-50% a year

**Structural context, from Micron's own 10-K:** "In the past five years, annual percentage
changes in DRAM average selling prices have ranged from plus low 40% to a minus high 40%
range. In the past five years, annual percentage changes in NAND average selling prices have
ranged from plus low 30% to a minus low 50% range... In some prior periods, average selling
prices for our products have been below our manufacturing costs." This is the company
stating, under legal liability, that the current windfall is a cycle position, not a new
steady state.
Source: [Micron FY2025 10-K risk factors, data/filings/MU/2026-09-20.json, filed 2025-10-03].

**Cyclical — currently in the acute up-leg.** DRAM contract prices rose ~90% in Q1 2026 and
58-63% QoQ in Q2 2026; Micron's fiscal Q3 2026 revenue hit $41.46B on this pricing
(reported 2026-06-24, "quadrupling of revenue" per CNBC). Analyst consensus on cycle-peak
timing has been pushed out repeatedly through 2026 — from "H1 2027" earlier in the year to
"no earlier than Q4 2027, possibly 2028" by mid-2026 — as AI/HBM demand keeps absorbing
supply, and Samsung/SK Hynix/Micron are reported to be showing more capital discipline than
in past cycles (resisting the urge to overbuild). Confidence: medium-high that this is a
genuine, unusually long up-cycle; low confidence in any specific peak-timing call, since
every prior "consensus" on this exact question has already shifted once in 2026 alone.
Source: [Blocksandfiles.com, "Memory semiconductor supercycle set to run through 2028,"
2026]; [useluminix.com, "DRAM Cycle Mid-2026 Update: Pricing, Inventory & Peak Timing," 2026].

**Structural, smaller — Chinese competition is real but currently at the trailing edge, not
the leading edge.** CXMT (China) is taking DRAM market share from Micron/Samsung/SK Hynix
(reported 2026-09-03), and a new Chinese memory IPO is adding competitive pressure
(2026-08-24). This mirrors the ASML DUV story: a real, growing domestic Chinese alternative,
not yet competitive at the highest-value end (HBM/leading-edge DRAM) where Micron's current
AI-cycle profits are concentrated.

**Cyclical/legal noise.** Price-fixing class actions against Micron, Samsung and SK Hynix
(filed June-July 2026, alleging the price surge itself is collusive rather than
supply/demand-driven) are a predictable byproduct of a fast price spike; no adjudicated
finding exists in the window reviewed.

**Open question.** No source addresses whether Micron's ~$250B committed US capacity buildout
(through 2035, per July 2026 announcements) will land supply increases during the up-cycle
(margin-accretive, well-timed) or during the eventual downturn (margin-destructive,
mistimed) — the answer determines whether this capex is structural moat-building or classic
late-cycle overbuild.

---

## ASML — a real long-term competitive crack has appeared, but the near-term price is unaffected

**Structural.** The Information reported 2026-07-27 that a Chinese state-backed company
(Shanghai Aishengna Electronic Technology Group, formed by absorbing teams from Yuliangsheng
and SMEE) has begun manufacturing an immersion DUV lithography machine — the first credible
sign of a domestic Chinese alternative to ASML for a real (if lower-end) tool category.
Production plans are small (about 5 machines in 2026, 20 in 2027, versus ASML's 131
equivalent immersion systems delivered in 2025 alone) and performance reportedly lags ASML
by roughly four generations; first units are headed to SMIC, Hua Hong and CXMT. This does
not threaten ASML's EUV monopoly (China is already barred from EUV tools by export controls)
but it does put a expiry date on how long China stays dependent on ASML for mid-tier DUV
tools, which is a real, if distant, erosion of ASML's addressable China revenue. The stock
fell as much as 8% on the report. Confidence: medium-high on the facts (multiple outlets,
including CNBC and Asia Times, converged on similar production numbers); the five-year
earnings impact is speculative given the reported four-generation gap.
Source: [CNBC, "China's reported chip breakthrough comes with some big caveats," 2026-07-28](https://www.cnbc.com/2026/07/28/china-chipmaking-duv-tool-asml-explained.html); [Asia Times, "China's DUV lithography still lags ASML by four generations," 2026-07].

**Is the price already paying for the strength? Partial evidence, not a full answer.**
Guidance has been raised repeatedly through 2026 (April, July) on order-book strength, and
ASML "won over" TSMC and Samsung for new EUV machines as of September 2026 — directly
reversing an April 2026 report that TSMC had declined to buy ASML's latest lithography tools
(a story that itself moved ASML shares down and TSM shares up at the time, on the theory
that TSM's delay would boost TSM's own margins). The reversal within five months suggests
the April "TSM says no" story was either a timing issue or a negotiating position, not a
durable order loss. Confidence: medium — the two data points (April decline, September
"wins over") are both single-sourced press reports, not confirmed order-book disclosures.
Source: [Stocktwits, "ASML Stock Drops After TSMC Says No To Latest Lithography Machines,"
2026-04-23]; [Bloomberg/Yahoo Finance, "ASML Wins Over TSMC, Samsung for New EUV Machines as
AI Demand Surges," 2026-09-08].

**Open question — the analyst's original framing (is the price already paying for the
strength) is not answered by the news itself.** No article in the window reconciles ASML's
repeated guidance raises against its starting valuation; that is a valuation-model question
(`tools/predict.py`), not a fact question, and the news scout's remit stops there.

---

## 7203.T Toyota — the scorecard's margin concern is confirmed by the company's own numbers; the model's optimism rests on the yen and hybrids holding

**Structural/cyclical (genuinely both) — US tariffs erased North America profitability
entirely in FY2026.** Per Toyota's own FY2026 results and multiple outlets (WardsAuto, CNBC,
Reuters, reported 2026-05-08/11), the total tariff impact was ¥1.4 trillion for the year,
producing a -1.4% operating margin in North America — Toyota's first North America loss in
16 years. FY2027 guidance points to a consolidated operating margin around 5.9%, with
operating income forecast near ¥3.0 trillion, down further from FY2026's ¥3.76-3.8 trillion,
even as revenue edges up. This is a structurally thin margin for a company of Toyota's
scale, and it validates the scorecard's D grade on margins directly — it is not a
mislabeled cyclical dip, it is Toyota's own multi-year guidance. Confidence: high (company
guidance, corroborated across four independent outlets).
Source: [WardsAuto, "US tariffs erase all of Toyota's North America profits in FY2026,"
2026-05-11]; [Investing.com, "Toyota FY2026 slides: tariffs drive profit decline despite
volume gains," 2026]; [CNBC, "Toyota fourth-quarter profit misses by wide margin as U.S.
tariffs drive 49% slump," 2026-05-08].

**Structural — Toyota is not chasing EV share; it cut its EV sales target by over 10% in
August 2026** while raising its overall profit forecast to ¥3.25 trillion (2026-08-04, per
Nikkei Asia/WSJ), explicitly citing hybrid demand and a weak yen as the offsets. Hybrids are
reported to be threatening GM's US sales crown (2026-06-24, Bloomberg), suggesting Toyota's
hybrid-first strategy — treated by some as a laggard EV strategy — is currently working
commercially, not just defensively. Whether this is a moat (Toyota's hybrid engineering lead)
or a hedge against an EV transition it is behind on is exactly the scorecard/model tension;
the news does not resolve it either way, it documents both sides.

**Structural, early-stage — a ¥3 trillion non-vehicle "value chain" profit target by 2030**
(used cars, subscriptions, safety add-ons; announced 2026-09-07) is a genuine
margin-diversification strategy away from new-vehicle sales, Toyota's stated response to
thin new-car margins. Too new to score as confirmed, but it is the company's own admission
that the core business's margin structure needs supplementing.
Source: [finance.biggo.com, "Toyota Aims to Break Reliance on New Car Sales, Targets ¥3
Trillion in Value Chain Profit by 2030," 2026-09-07].

**Cyclical, not structural.** The Kyushu earthquake disrupting the auto/chip supply chain
(late July 2026) and the recall of over 500,000 vehicles (2026-08-12) are operational events
with no evidence of recurring or structural cause in the sources reviewed.

**Open question.** No source in the window quantifies the counterfactual: what Toyota's
margin looks like at a "normal" (non-crisis) yen rate, separating the currency tailwind from
underlying operational improvement. That decomposition would tell you whether the model's
optimism is betting on yen weakness persisting (a macro call, not a company call) or on real
margin recovery.

---

## AMZN — AWS/AI is executing; the legal overhang is new and large but not yet a moat question

**Structural, positive — AWS's AI/chip business reached a roughly $25B annual run rate**
(disclosed on the Q2 2026 earnings call, reported 2026-07-31), with AWS growth accelerating
and Amazon crossing a $3 trillion market cap for the first time (2026-08-03). Capex for 2026
was raised to $220B specifically citing higher memory costs (2026-07-30) — a direct link to
the DRAM price spike documented in the MU section above, meaning Amazon's own AI buildout
cost is being inflated by the same supercycle that is inflating Micron's profits.
Source: [CNBC, "Amazon tops $3 trillion market cap as stock continues post-earnings surge,"
2026-08-03]; [CNBC, "Amazon hikes 2026 capex to $220 billion due to higher memory costs,"
2026-07-30].

**Structural, negative, unresolved — the FTC and 22 states sued Amazon on 2026-08-31**
alleging Amazon secretly inflated ad prices, taking roughly $20B via undisclosed surcharges
in its ad-auction business. This is a second major FTC action against Amazon (following the
earlier Prime "dark patterns" case) and, if it results in a structural remedy to the ad
auction mechanism, could affect a high-margin, fast-growing part of the business. As of
2026-09-20 it is an allegation, not a finding. Confidence: the filing itself is confirmed by
multiple outlets (Reuters, Washington Post, Bloomberg); the five-year earnings impact is
entirely dependent on an outcome not yet known.
Source: [Reuters, "Amazon sued by FTC, 22 US states over ad sales practices,"
2026-08-31]; [Washington Post, "Amazon secretly inflated ad prices, the FTC and 22 states
allege in a lawsuit," 2026-08-31].

**Structural, small but genuine — Amazon Supply Chain Services**, launched 2026-05-04-08,
opens Amazon's internal logistics network to third-party businesses, a direct new
competitive entry against UPS and FedEx. Too early to size, but it is a real new revenue
category built on an existing asset, not a pivot requiring new capital.

**Cyclical/noise.** The pregnant-worker discrimination lawsuit (2026-09-08) and the
wrongful-death suit from a cargo plane crash (2026-09-09) are legal/reputational, not
thesis-moving. The Globalstar acquisition (~$11.6B, closed by mid-2026) is a modest
satellite/connectivity bolt-on, not yet material at Amazon's scale.

**Open question.** No source quantifies what fraction of the $220B 2026 capex is AWS/AI
versus fulfillment-network buildout, which is the split that would show whether the model's
+18.1% optimism is really an AWS bet or a broader e-commerce-margin bet.

---

## Cross-cutting notes on method

**Duplication observed.** Several stories were counted many times by outlet, not by fact:
the NVIDIA/Groq DOJ probe (5+ outlets, one fact), the Meta child-safety settlement (10+
state-AG press releases plus national wire coverage, one fact), the TSMC/Amkor Arizona
packaging deal (4+ near-identical writeups), and the ASML China DUV story (8+ outlets
covering one Information report). Treating each of these as independent confirmation would
overstate how much reporting actually exists.

**Absences worth flagging (an absence is itself a finding):**
- **TSM:** no article in 180 days documents an actual geopolitical escalation — the
  structural risk this ticker exists to flag has not moved in either direction; only TSMC's
  own hedges (Arizona, Japan, Germany) have.
- **AVGO:** no source, including Broadcom's own disclosures, breaks out AI revenue by named
  customer — the concentration is inferred from trade press, not confirmed by the company.
- **ASML/7203.T:** no source resolves the valuation-vs-strength or margin-vs-yen questions
  the analyst's brief asked about; the news documents both sides of each disagreement without
  settling it, which is itself informative about where the market's uncertainty actually sits.
- **ARM:** no source splits forward growth between the legacy licensing business and the new
  AGI CPU line, which is the split that would show whether the FTC risk sits in a separable
  part of the business.

**Article count.** Ten `fetch_news.py` pulls returned 157 (NVDA) + 186 (TSM) + 185 (META) +
177 (AVGO) + 190 (LLY) + 108 (ARM) + 180 (MU) + 103 (ASML) + 157 (7203.T) + 189 (AMZN) =
**1,632 articles reviewed** (after the tool's own within-ticker deduplication). Of these,
roughly **28 items were judged structural** (the ones quoted above, several of which are
themselves single facts covered by multiple outlets), **~20-25 were cyclical** (earnings
beats/misses, guidance raises tied to the current demand or memory cycle, one-off weather/
supply disruptions, litigation with no structural remedy attached), and **the large majority
— well over 1,500 items, roughly 90%+ of the feed** — was noise: daily stock-price
commentary, "X stock could be worth $Y by 2030" prediction pieces, analyst price-target
resets, "is it a buy" listicles, and keyword mismatches (the ARM ticker in particular pulled
many irrelevant "arm" stories — a woman's arm injury, the US Army, robotic arms — because
`fetch_news.py`'s tagging is keyword-based, exactly as the tool's own documentation warns).
