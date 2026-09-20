---
name: stock-research
description: Run the full five-year research pipeline on international stocks - collect fundamentals and filings, sweep news and macro, score against absolute bands and sector peers, model the growth fade, and write the investment thesis. Also ranks funds and ETFs on their own terms and checks them for overlap with the stocks already held. Use when asked to research, analyse, compare, or screen stocks or funds for a multi-year horizon, or to refresh the watchlist. Handles one ticker or the whole universe.
---

# Five-year equity research pipeline

Four specialist agents and a set of deterministic tools. The tools fetch and
compute, so the numbers are reproducible. The agents read and judge, so the
analysis is not a spreadsheet pretending to be a view.

## The order, and why it is this order

Collection before analysis, always. The most common failure in this kind of work
is an analysis written over a gap in the data that nobody noticed.

**1. Data.** Launch `stock-data-collector` with the tickers. It fetches
statements and filings and returns a coverage report naming what is missing.
Read that report before continuing. If a ticker has under three years of data or
a hole in its revenue series, every growth rate for it is unreliable and the
analysis has to say so.

**2. Context and story, in parallel.** Launch `news-scout` and `macro-analyst` at
the same time; neither depends on the other. The scout triages news into what
changes five-year earnings power and what only moves the price. The macro agent
maps rates, trade policy, capital cycles and regulation onto the specific
holdings.

**3. Score, then place the score.** Run these yourself, they take seconds:

```bash
uv run python tools/score.py <TICKERS...> --rank
uv run python tools/peers.py <TICKER>                  # where it sits in its sector
uv run python tools/predict.py <TICKERS...>            # fade, Monte Carlo, report
uv run python tools/build_report.py <TICKERS...> --name <slug>
```

`score.py` grades against fixed bands, which is what makes a Thai bank and a US
software company comparable at all. A band cannot know what is normal for an
industry, though: a 75% gross margin is unremarkable in software and remarkable
in autos, and both collect the same points. `peers.py` answers the other half,
and its `disagreements` list is the part worth reading - a metric that scores
well absolutely while sitting at its sector median means the company is riding
an industry rather than beating one. Check `reliable` before quoting any
percentile; under four companies in a group makes it arithmetic without meaning.

**4. Thesis.** Launch `equity-analyst` with the data pack path and the briefs.
It writes the five-year case with an explicit bull and bear.

Steps 1 and 2 can overlap when data already exists on disk from today. Step 4
cannot start before the rest have finished, since its whole job is to reconcile
them.

## Any stock on earth, not just the watchlist

Coverage is every symbol Yahoo Finance indexes, which is essentially every major
exchange worldwide. `config/universe.yaml` is a shortcut for names tracked
regularly, not a boundary on what can be researched.

When the request names a company rather than a symbol, resolve it first and say
which listing you took:

```bash
uv run python tools/search_tickers.py "Toyota"
uv run python tools/search_tickers.py "Toyota" --exact
```

A home listing and its US ADR are different instruments. The ADR trades in
dollars while the statements stay in the home currency, and that mismatch breaks
any ratio built from market cap over a statement line item. The tools detect it
and correct for it, but the choice of listing still belongs in the report.

## Funds are not companies

A fund has no income statement. Revenue growth, margins and ROIC do not exist
for it, so four of the five equity pillars have nothing to measure. Never run an
ETF through `score.py` or quote `fetch_fundamentals.py` for one - the output
will be mostly empty and the parts that are not are meaningless.

```bash
uv run python tools/fetch_funds.py                     # every fund in universe.yaml
uv run python tools/fetch_funds.py QQQ VOO             # or named funds, or a fund group
uv run python tools/score_funds.py --rank              # the league table
uv run python tools/score_funds.py --overlap QQQ       # vs the stocks tracked here
uv run python tools/score_funds.py --overlap VOO QQQ   # two funds against each other
```

Funds are scored on cost, risk-adjusted history, concentration, size and yield.
Cost carries more weight than past return deliberately: the expense ratio is the
only number known in advance, and it predicts future relative performance more
reliably than past performance does. Say that when the ranking surprises someone.

Run the overlap check whenever someone is considering adding a fund. Buying an
index on top of the names inside it is the most common way a portfolio becomes
concentrated while looking diversified, and nothing in a fund's name reveals it.
Both overlap checks read published top-ten holdings only, so the number is a
floor on duplication, never the whole picture.

Read `category` before the rank. A bond fund and an equity fund do not compare
on risk - 6% volatility is unremarkable for bonds and extraordinary for equities
- the same way the equity side needs peer context beside its absolute bands.

## Running the tools directly

```bash
# One ticker, or many, or a group from config/universe.yaml, or the whole watchlist
uv run python tools/fetch_fundamentals.py NVDA MSFT
uv run python tools/fetch_fundamentals.py ai_infra
uv run python tools/fetch_fundamentals.py

uv run python tools/fetch_news.py NVDA --days 90
uv run python tools/fetch_news.py --macro --days 30
uv run python tools/fetch_filings.py NVDA --risk-factors

uv run python tools/score.py --all --rank
uv run python tools/peers.py --sectors
uv run python tools/predict.py NVDA --runs 20000
uv run python tools/predict.py ai_infra --report-name ai
uv run python tools/build_report.py --all --name full-universe
```

Groups and the watchlist live in `config/universe.yaml`. Any tool accepts a group
name where it accepts tickers.

Credentials live in `.env` at the repo root and load themselves; no export is
needed. EDGAR wants a real contact in `REPORTSTOCK_UA` and throttles anonymous
traffic instead of refusing it, so an unset one looks like a company that never
filed. `fetch_filings.py` says so on startup when it is not configured.

## Scope shapes the work

**One ticker, deep.** All four agents, 365 days of news, filings with risk
factors. Expect a real report.

**A comparison of five to ten names.** All four agents, but tell the scout to
cover the group in one pass rather than one ticker at a time. The ranking is the
point, so the analyst must say which it would rather own.

**Screening the whole universe.** Skip the per-ticker news sweep, which is slow
and mostly wasted at this stage. Run fundamentals and scoring across everything,
rank, then send only the top names and any surprising ones through the full
pipeline. A low score that you expected to be high is worth investigating.

**A fund or a portfolio-shaped question.** Fetch and rank the funds, then run
the overlap check against whatever the user already holds before saying anything
about diversification. Skip the news and filings agents; there is no Item 1A for
an index, and fund-level news is almost always about flows rather than about the
five-year outcome.

**A refresh of existing work.** Snapshots are dated and never overwritten across
days. Re-run collection, then have the analyst compare against the previous
report and write only what changed and why. That is far more useful than
regenerating the same document.

## Things that will otherwise go wrong

The scorecard rewards what already happened. It cannot see a business changing
shape, which over five years is usually what decides the outcome. Treat a high
score as a reason to look closely, never as a conclusion.

A home listing outside the US has no SEC filing at all, but a foreign company
with a US listing files a 20-F, and the tool reads that layout too. What comes
back can still be a pointer rather than a section: some filers incorporate their
risk factors by reference, which arrives flagged rather than silently empty. Say
which of the three situations applies rather than letting a US name look better
documented because it is more documented.

Banks and insurers break several ratios in the schema. Net debt and EV/EBITDA
mean little for a bank, and its composite score is not comparable to an
industrial's.

Several holdings can be one position wearing different names. A basket whose
growth all rests on the same capital spending cycle is concentrated however many
tickers it contains. The analyst is asked to check this; make sure it does.

A modelled return is arithmetic on stated assumptions, not a forecast. Never
report `Base 5y/yr` as an expected return, and never call `predict.py` output a
forecast either. It has never been validated out of sample and cannot be with
this data source: yfinance serves current data with no point-in-time history, so
an honest backtest is impossible. The percentiles describe the spread of the
assumptions, nothing about the world.

A percentile from `peers.py` over a group of two or three is arithmetic without
meaning. The tool reports `reliable` for exactly this reason; read it.

Yahoo Finance is delayed and revises. Fine for five-year structural comparison,
not for anything time-sensitive.

## Output

Everything is written to disk, dated, and traceable to its snapshot:

```
data/raw/<TICKER>/<date>.json         statements, ratios, market data
data/news/<TICKER>/<date>.json        collected articles, tagged
data/news/<TICKER>/brief-<date>.md    the scout's triage
data/news/_macro/<date>.json          macro sweep
data/filings/<TICKER>/<date>.json     SEC filings and Item 1A text
data/scores/<TICKER>/<date>.json      pillar scores and scenarios
data/predictions/<TICKER>/<date>.json    fitted fade, Monte Carlo, sensitivity
data/funds/<FUND>/<date>.json            fund costs, risk, holdings, sectors
data/fund_scores/<FUND>/<date>.json      fund pillar scores and overlap
data/reports/<date>-<slug>-datapack.md   assembled facts, no judgement
data/reports/<date>-macro-brief.md       the macro read
data/reports/<date>-<slug>-prediction.md the model run, written every time
data/reports/<date>-<slug>-thesis.md     the investment case
```

The split between the data pack and the thesis is deliberate. Facts and
judgement live in separate files so that any claim in the thesis can be checked
against the pack it came from.

## The browser app

```bash
uv run python -m streamlit run app.py
```

Use the module form, not the bare `streamlit` command, which Windows Application
Control blocks on this machine.

The app reads and writes the same dated snapshots under `data/`, so a ticker
pulled in the browser is immediately available here and anything collected here
shows up there. It is a second window onto one set of files, not a second system.
When a user says they already loaded a stock, check `data/raw/` before fetching
it again.

This is research tooling, not investment advice. Say so in anything that leaves
the repository.
