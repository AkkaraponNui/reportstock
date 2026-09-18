# reportstock

Five-year investment research on international equities. Deterministic Python
tools fetch and compute; four Claude Code sub-agents read and judge.

## Run anything with uv

`uv run python tools/<tool>.py` — never bare `python`, the dependencies live in
the project venv. Windows shell here is PowerShell, with Git Bash also available.

## The pipeline

Invoke the `stock-research` skill for the full flow. It sequences the agents and
explains scope choices. In short: collect, then sweep news and macro in parallel,
then score, then write the thesis.

Agents, in `.claude/agents/`:

| Agent | Does | Model |
|---|---|---|
| `stock-data-collector` | statements, filings, coverage validation | sonnet |
| `news-scout` | triages news into structural / cyclical / noise | sonnet |
| `macro-analyst` | rates, trade, capital cycles mapped to tickers | sonnet |
| `equity-analyst` | the five-year thesis, bull and bear | opus |

## Tools

```bash
uv run python tools/search_tickers.py "Toyota"        # any company on earth -> ticker
uv run python tools/fetch_fundamentals.py NVDA MSFT   # or a group, or blank for the watchlist
uv run python tools/fetch_news.py NVDA --days 90
uv run python tools/fetch_news.py --macro --days 30
uv run python tools/fetch_filings.py NVDA --risk-factors
uv run python tools/peers.py NVDA                      # where it sits in its sector
uv run python tools/peers.py --sectors                 # sector medians and group sizes
uv run python tools/score.py --all --rank
uv run python tools/predict.py NVDA --runs 20000      # Monte Carlo + sensitivity + report
uv run python tools/predict.py ai_infra --report-name ai   # one comparison report
uv run python tools/predict.py NVDA --no-report       # JSON only
uv run python tools/predict.py --fit-only             # just the fitted fade curve
uv run python tools/build_report.py --all --name full-universe
```

Any tool takes tickers, a group name from `config/universe.yaml`, or nothing at
all (meaning the whole watchlist).

Coverage is every symbol Yahoo Finance indexes, not the watchlist. That file is a
shortcut for names tracked regularly, never a boundary. Suffixes follow Yahoo:
`.BK` Thailand, `.T` Tokyo, `.HK` Hong Kong, `.KS` Korea, `.L` London, `.SW`
Zurich, `.AS` Amsterdam, `.NS` India, `.TO` Toronto, `.AX` Australia. When a user
names a company rather than a symbol, resolve it with `search_tickers.py` instead
of guessing, and say which listing you picked: a home listing and its US ADR are
different instruments with different currencies.

## Streamlit app

```bash
uv run python -m streamlit run app.py
```

Use `python -m streamlit`, not the bare `streamlit` command. Windows Application
Control blocks the console-script shim on this machine, and the module form is
the documented workaround.

`app.py` is the entry point; pages live in `ui/`. The app calls the same tool
functions and writes the same dated snapshots under `data/`, so anything fetched
in the browser is immediately visible to the agents and the other way round.
There is no separate database and no second copy of the logic.

EDGAR requires a contact string: `export REPORTSTOCK_UA="name you@example.com"`.
Optional keys that add news depth: `FINNHUB_API_KEY`, `ALPHAVANTAGE_API_KEY`.
Everything works without them.

## Deployment

`DEPLOY.md` covers the free hosting options and their trade-offs. Two constraints
shape every answer there, so repeat them rather than letting someone rediscover
them:

Yahoo Finance rate-limits and sometimes blocks datacenter IP ranges. The same
fetch that works from a home connection can return 429, 401, or silently empty
data from a cloud host. This has not been verified from this machine, which is on
a residential IP, so present it as a known risk rather than a measured fact.

Free tiers use ephemeral filesystems, so `data/` empties on every restart. That
turns the dated snapshots from an audit trail into a cache and quietly removes
the property the whole design rests on.

`APP_PASSWORD` turns on a shared-password gate in `ui/auth.py`. Unset means no
gate, which is correct locally and wrong on a public URL.

Regenerate `requirements.txt` after any dependency change:
`uv export --no-hashes --no-dev --no-annotate --no-header --format requirements-txt > requirements.txt`

## The prediction model and the chat agent

`tools/predict.py` fits growth persistence across the panel of tickers on disk,
then runs a Monte Carlo over growth, margin and exit multiple. Two things about it
are load-bearing and easy to misreport.

It has never been validated out of sample, and cannot be with this data source:
yfinance serves current data with no point-in-time history, so an honest backtest
is impossible. Say that rather than calling the output a forecast. The percentiles
describe the spread of the assumptions, not a probability of anything in the world.

Every run writes a markdown report through `tools/predict_report.py`, one per
ticker or a comparison when several ran together. The JSON is for machines; the
report is what anyone actually reads, so keep the two in step when the schema
changes. Sensitivity levers carry both `lever` (Thai) and `lever_en`, so a report
picks the label matching its own language rather than translating at render time.

The fade is fitted twice, on all points and on a set trimmed of hypergrowth years,
because in a panel this small two extreme points drag the regression line and
inflate R-squared. The trimmed fit is used and the disagreement between the two is
carried into the slope's standard error. If you re-tune this, keep both fits.

`tools/chat_agent.py` is Claude with eleven read-only tools over the same
snapshots plus one with a side effect (`fetch_stock_data`). It uses
`claude-opus-5` with adaptive thinking and effort in `output_config`. The system
prompt's first rule is that it must read a file before quoting a number, because
its own training data has a cutoff and the files carry dates. Keep that rule if
you edit the prompt.

The chat page needs `ANTHROPIC_API_KEY` (or an `ant auth login` profile); every
other page works without one, so never make a credential a hard requirement of
the app as a whole.

## Tests

`uv run pytest`. They are fast and have no network dependency; the chat loop runs
against a fake client, so no API key is needed.

Every test in `tests/` exists because a real bug shipped past review. None of them
crashed anything: a currency mismatch that inflated an ADR's return by the
exchange rate, a margin ceiling that silently capped high-margin businesses, a
bull case that landed below its own base case, a regression dominated by two
outliers, sensitivity levers rendered inert by a binding clamp, and an exit
multiple anchored on forward P/E while the entry price came from trailing P/E,
which made an expensive stock score better than a cheap one. Wrong numbers that
look plausible are the only failure mode that matters here. Add a test whenever
you touch `BANDS`, `PILLARS`, `project`, `simulate`, or `sensitivity`.

## Total return, not price return

Dividends are part of the answer. `score.py` reports `price_return_annualized`
and `dividend_contribution` separately and combines them multiplicatively;
`predict.py` samples the yield with a cut probability that rises when the payout
exceeds earnings. Leaving dividends out biases every comparison one way: against
mature payers, toward companies that retain everything.

Yahoo's `dividendYield` is a percentage number, not a fraction. Microsoft comes
back as `0.8` meaning 0.80%. `fetch_fundamentals.dividend_yield_fraction`
normalizes it, preferring `dividendRate / price`, which is unambiguous. Anything
reading the raw field directly is off by 100x.

## Absolute bands and peer context are two different questions

`score.py` grades on fixed bands, which is what makes companies comparable across
the universe. The cost is that a band cannot know what is normal for an industry:
a 75% gross margin is ordinary in software and extraordinary in autos, and both
collect the same points. `tools/peers.py` supplies the other half, and the part
worth reading is `disagreements` - where a metric scores well absolutely but sits
at its sector median, meaning the company is riding an industry rather than
beating one. Report both, and check `reliable` before quoting a percentile: fewer
than four companies in a group makes the number arithmetic without meaning.

## Conventions that matter

Snapshots are dated and never overwritten across days. `data/raw/NVDA/2026-09-17.json`
is what was known on that date, and keeping it is how a past conclusion can be
judged against the evidence that existed when it was made. Do not clean these up.

Facts and judgement live in separate files. `build_report.py` emits a data pack
with no opinion in it; the analyst agent writes the thesis separately. Any claim
in a thesis must be checkable against the pack.

The scorecard in `tools/score.py` is a fixed yardstick, with its bands and
weights in `BANDS` and `PILLARS`. Change them deliberately and re-score
everything, since a score is only comparable against others computed the same way.

A projected return is arithmetic on stated assumptions, not a forecast. Never
report it as an expected return.

## Data limits to state, not hide

Yahoo Finance is delayed and revises. Adequate for structural comparison over
years, not for anything time-sensitive.

Non-US tickers (`7203.T`, `0700.HK`, `NESN.SW`, `005930.KS`) have no SEC filings,
so risk-factor evidence is uneven across a mixed universe.

`roic_est` uses a flat 21% tax haircut, not a real effective rate. It ranks; it
does not measure.

Banks and insurers break net debt, EV and EV/EBITDA. Their composite scores are
not comparable to an industrial's.

News tagging is keyword matching and mislabels articles regularly. It is a first
pass for filtering, never a verdict.

## Boundaries

This is research tooling. It does not place trades, and nothing it produces is
investment advice. Anything that leaves the repository says so.
