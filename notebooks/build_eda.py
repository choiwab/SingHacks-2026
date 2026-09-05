# ruff: noqa: E501
# Line length is exempted here only: every long line is notebook cell source or markdown prose
# held in a string literal, where wrapping would change what the reader sees in the notebook.
"""Build notebooks/eda.ipynb with nbformat.

Run:  uv run python notebooks/build_eda.py
Then: uv run jupyter execute --inplace notebooks/eda.ipynb
"""

from pathlib import Path

import nbformat as nbf

CELLS: list[tuple[str, str]] = []


def md(text: str) -> None:
    CELLS.append(("md", text.strip("\n")))


def code(text: str) -> None:
    CELLS.append(("code", text.strip("\n")))


# ---------------------------------------------------------------- 0. title
md("""
# Phase A — Exploratory Data Analysis

**SingHacks 2026 · Julius Baer wealth intelligence · dataset in `data/`**

One relationship manager, Priscilla Ong, looks after 20 clients holding 24 portfolios.
Positions are given at **five dated snapshots**, the last of which (2026-08-26) is "today".

### How to read this notebook

Every section follows the same three lines:

- **What we check** — the question being asked of the data.
- **Why it matters** — what an answer changes for the product we are building.
- **What we found** — the actual result, with numbers, written after the code below it ran.

Sections 1–2 establish that the data is trustworthy. Sections 3–10 extract the signals.
Section 11 lists every flaw we found. Section 12 is the handoff: the exact list of signals the
automated pipeline should compute.

Two words used throughout:

- **Snapshot** — one of the five dates positions are reported at.
- **Household** — a client's portfolios added together. Some clients hold more than one.
""")

# ---------------------------------------------------------------- setup
code('''
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def find_data() -> Path:
    """Locate data/ whether the notebook runs from repo root or from notebooks/."""
    for base in [Path.cwd(), *Path.cwd().parents]:
        if (base / "data" / "holdings.csv").exists():
            return base / "data"
    raise FileNotFoundError("could not find data/holdings.csv")


DATA = find_data()

SNAPSHOTS = ["2025-12-31", "2026-02-27", "2026-03-31", "2026-06-30", "2026-08-26"]
FIRST, LAST = SNAPSHOTS[0], SNAPSHOTS[-1]
TODAY = LAST
ASSET_CLASSES = [
    "Cash and Equivalents",
    "Fixed Income",
    "Equity",
    "Alternatives",
    "Commodities",
    "Structured Products",
]

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 60)
pd.set_option("display.max_colwidth", 70)
plt.rcParams["figure.figsize"] = (10, 5)
plt.rcParams["figure.dpi"] = 110
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3


def load(filename: str) -> pd.DataFrame:
    """Read one source file. JSON comes back as a DataFrame too."""
    path = DATA / filename
    if path.suffix == ".json":
        return pd.DataFrame(json.loads(path.read_text()))
    return pd.read_csv(path)


FILES = [
    "clients.csv",
    "portfolios.csv",
    "holdings.csv",
    "instruments.csv",
    "mandates.csv",
    "transactions.csv",
    "credit_facilities.csv",
    "commitments.csv",
    "planned_cash_needs.csv",
    "market_context.csv",
    "event_log.csv",
    "rm_notes.json",
]

src = {f.rsplit(".", 1)[0]: load(f) for f in FILES}

clients = src["clients"]
portfolios = src["portfolios"]
holdings = src["holdings"]
instruments = src["instruments"]
mandates = src["mandates"]
transactions = src["transactions"]
facilities = src["credit_facilities"]
commitments = src["commitments"]
cash_needs = src["planned_cash_needs"]
market = src["market_context"]
events = src["event_log"]
notes = src["rm_notes"]

NAME = clients.set_index("client_id")["client_name"].to_dict()
BASE_CCY = clients.set_index("client_id")["base_currency"].to_dict()

# FX at each snapshot, quoted the way market_context quotes it.
FX = (
    market[market["category"] == "FX"]
    .pivot_table(index="snapshot_date", columns="series_id", values="value")
)


def to_usd(amount: float, ccy: str, date: str = TODAY) -> float:
    """Convert an amount to USD using market_context rates for that snapshot."""
    if ccy == "USD":
        return float(amount)
    row = FX.loc[date]
    if f"{ccy}USD" in row.index:  # EURUSD, GBPUSD are quoted USD per unit
        return float(amount) * float(row[f"{ccy}USD"])
    return float(amount) / float(row[f"USD{ccy}"])


def name_of(client_id: str) -> str:
    return NAME.get(client_id, client_id)


print(f"data directory : {DATA}")
print(f"sources loaded : {len(src)}")
print(f"snapshots      : {', '.join(SNAPSHOTS)}  (today = {TODAY})")
''')

# ---------------------------------------------------------------- 1. profile
md("""
## 1. File-by-file profile

**What we check.** Size, shape, missing values and duplicates for all 12 source files, plus a look
at a few real rows.

**Why it matters.** In a private bank the position file is the record of what a client owns, and
everything downstream — the valuation, the suitability test, the tax pack — is derived from it. We
need to know which fields are always populated before we compute anything, because a suitability
check that silently skips a position is worse than no check at all. Nulls also mark where the
operational seams are: a missing cost basis almost always means an asset was transferred in from
another institution, and that one fact changes what advice is even possible for that client.

**What we found.** 12 files, 1,703 rows across the tabular sources. The data is cleaner than
production banking data usually is: **no duplicate rows in any file**, and only 12 columns anywhere
contain a null. Most of those nulls are structural rather than missing data:

- `transactions` accounts for 901 of them, and all are expected — a dividend or a management fee has
  no quantity or price, and 65 of the 393 rows are portfolio-level cash movements with no instrument.
- `instruments.underlying_reference` is null for 53 of 62 instruments, because only structured
  products and a few specials reference an underlying.

That leaves three genuinely missing things, all of which turn out to matter: `clients.age` is null
once (Fong Enterprises is a legal entity, not a person); `holdings.sector` is null for 5 rows; and
5 rows have no cost basis at all. The last two belong to just **two instruments inside one
portfolio, PF-0005** — which section 11 shows is a portfolio transferred in from another bank.

> **Pipeline action.** Stage S1 (ingest) coerces types and parses dates explicitly rather than
> letting pandas infer them, and stage S2 (validate) records every null as a tagged observation
> instead of dropping the row. Nulls that are structural (a dividend has no quantity) are
> allow-listed by `(file, column)`; anything else is written to `data_quality_report.json` with its
> row reference. No row is ever silently discarded.
""")

code("""
def profile(filename: str, df: pd.DataFrame) -> dict:
    nulls = df.isna().sum()
    return {
        "file": filename,
        "rows": len(df),
        "cols": df.shape[1],
        "duplicate_rows": int(df.duplicated().sum()),
        "cols_with_nulls": int((nulls > 0).sum()),
        "null_cells": int(nulls.sum()),
        "first_columns": ", ".join(df.columns[:3]),
    }


profile_table = pd.DataFrame([profile(f, src[f.rsplit(".", 1)[0]]) for f in FILES])
profile_table
""")

code("""
# Every column in the dataset that contains a null, and how many.
null_report = []
for filename in FILES:
    df = src[filename.rsplit(".", 1)[0]]
    nulls = df.isna().sum()
    for column, n in nulls[nulls > 0].items():
        null_report.append(
            {"file": filename, "column": column, "nulls": int(n), "of_rows": len(df)}
        )

pd.DataFrame(null_report)
""")

code("""
# Column dtypes, grouped so we can see the shape of each file without 12 walls of output.
dtype_rows = []
for filename in FILES:
    df = src[filename.rsplit(".", 1)[0]]
    counts = df.dtypes.astype(str).value_counts()
    dtype_rows.append({"file": filename, **{k: int(v) for k, v in counts.items()}})

pd.DataFrame(dtype_rows).fillna(0).set_index("file").astype(int)
""")

code("""
# Sample rows from the three files everything else hangs off.
print("HOLDINGS (the centre of gravity)")
display(
    holdings.loc[
        holdings["snapshot_date"] == TODAY,
        [
            "snapshot_date", "portfolio_id", "client_id", "instrument_id", "asset_class",
            "quantity", "price_local", "market_value_base", "market_value_usd",
            "weight_pct", "liquidity_tier",
        ],
    ].head(4)
)

print("\\nINSTRUMENTS")
display(
    instruments[
        ["instrument_id", "instrument_name", "asset_class", "currency",
         "liquidity_tier", "concentration_limit_applies", "sustainability_excluded"]
    ].head(4)
)

print("\\nRM NOTES")
display(notes[["note_id", "client_id", "note_date", "channel"]].head(4))
""")

code("""
# Category values we will rely on later. Worth reading once.
print("asset classes   :", sorted(holdings["asset_class"].unique()))
print("liquidity tiers :", sorted(holdings["liquidity_tier"].unique()))
print("service models  :", sorted(portfolios["service_model"].unique()))
print("mandate codes   :", sorted(mandates["mandate_code"].unique()))
print("risk profiles   :", sorted(clients["risk_profile"].unique()))
print("txn types       :", sorted(transactions["transaction_type"].unique()))
print()
print("clients:", len(clients), " portfolios:", len(portfolios), " instruments:", len(instruments))
print("clients holding more than one portfolio:")
multi = portfolios.groupby("client_id").size()
display(
    multi[multi > 1]
    .rename("portfolios")
    .reset_index()
    .assign(client_name=lambda d: d["client_id"].map(NAME))
)
""")

# ---------------------------------------------------------------- 2. joins
md("""
## 2. Join-key integrity

**What we check.** Does every foreign key find its parent? Holdings to portfolios, portfolios to
clients, holdings to instruments, transactions to portfolios, facilities to portfolios, notes to
clients. We also check the reverse — parents with no children — and whether the client id that is
denormalised onto `holdings` agrees with the one on `portfolios`.

**Why it matters.** Client reporting is built by joining these tables, and the bank is accountable
for every number it puts in front of a client. An inner join that quietly drops an orphan position
understates that client's wealth and can hide a breach — the kind of error that surfaces in a
regulatory review rather than in testing. Reconciling the sum of positions back to the reported
account value is the standard control for exactly this: if the parts do not add up to the whole,
the whole is wrong and nothing built on it can be defended.

**What we found.** **Referential integrity is perfect — zero orphans on every join, in both
directions.** All 1,015 holdings map to the 24 portfolios; all 24 portfolios map to 20 clients;
all 62 instruments are held by someone and every held instrument is described; all 393 transactions
and all 5 credit facilities point at real portfolios; all 28 RM notes point at real clients. The
denormalised `holdings.client_id` agrees with `portfolios.client_id` on every row. We also
reconciled the money: **the sum of `holdings.market_value_base` equals the `aum_<date>` column in
`portfolios.csv` to within a cent for all 120 portfolio-snapshot pairs**, and the sum of
`portfolios.aum_usd_current` equals `clients.total_aum_usd` for all 20 clients. Inner joins are
safe here.

> **Pipeline action.** Stage S2 (validate) runs these same checks and **fails closed**: if any
> orphan, duplicate key or reconciliation break appears, the run raises with a diagnostic list
> rather than publishing a partial bundle. The repo already has this shape in
> `app/pipeline/sources.py` (`load_sources` raises `SourceValidationError` carrying
> `SourceDiagnostic` rows); the two additions needed are the **AUM reconciliation** check
> (`sum(holdings.market_value_base)` vs `portfolios.aum_<date>`, tolerance USD 0.01) and the
> **quantity × price** check, neither of which is currently validated.
""")

code("""
def join_check(label, left, right):
    left_set, right_set = set(pd.Series(left).dropna()), set(pd.Series(right).dropna())
    orphans = sorted(left_set - right_set)
    return {
        "join": label,
        "distinct_keys": len(left_set),
        "matched": len(left_set & right_set),
        "orphans": len(orphans),
        "example_orphan": orphans[0] if orphans else "-",
    }


join_table = pd.DataFrame([
    join_check("holdings.portfolio_id -> portfolios", holdings["portfolio_id"], portfolios["portfolio_id"]),
    join_check("holdings.client_id -> clients", holdings["client_id"], clients["client_id"]),
    join_check("holdings.instrument_id -> instruments", holdings["instrument_id"], instruments["instrument_id"]),
    join_check("portfolios.client_id -> clients", portfolios["client_id"], clients["client_id"]),
    join_check("portfolios.mandate_code -> mandates", portfolios["mandate_code"], mandates["mandate_code"]),
    join_check("transactions.portfolio_id -> portfolios", transactions["portfolio_id"], portfolios["portfolio_id"]),
    join_check("transactions.instrument_id -> instruments", transactions["instrument_id"], instruments["instrument_id"]),
    join_check("facilities.collateral_portfolio_id -> portfolios", facilities["collateral_portfolio_id"], portfolios["portfolio_id"]),
    join_check("commitments.portfolio_id -> portfolios", commitments["portfolio_id"], portfolios["portfolio_id"]),
    join_check("cash_needs.client_id -> clients", cash_needs["client_id"], clients["client_id"]),
    join_check("rm_notes.client_id -> clients", notes["client_id"], clients["client_id"]),
    # reverse direction: parents with no children
    join_check("portfolios -> appear in holdings", portfolios["portfolio_id"], holdings["portfolio_id"]),
    join_check("clients -> own a portfolio", clients["client_id"], portfolios["client_id"]),
    join_check("instruments -> held by someone", instruments["instrument_id"], holdings["instrument_id"]),
])
join_table
""")

code("""
# Is the client_id denormalised onto holdings consistent with portfolios.csv?
check = holdings.merge(
    portfolios[["portfolio_id", "client_id"]], on="portfolio_id", suffixes=("_h", "_p")
)
mismatch = check[check["client_id_h"] != check["client_id_p"]]
print(f"holdings rows where client_id disagrees with portfolios.csv: {len(mismatch)}")

# Does the sum of holdings equal the reported AUM, at every snapshot?
aum_long = portfolios.melt(
    id_vars=["portfolio_id"],
    value_vars=[f"aum_{d}" for d in SNAPSHOTS],
    var_name="col",
    value_name="reported_aum",
).assign(snapshot_date=lambda d: d["col"].str.removeprefix("aum_"))

recon = (
    holdings.groupby(["portfolio_id", "snapshot_date"], as_index=False)["market_value_base"].sum()
    .merge(aum_long, on=["portfolio_id", "snapshot_date"], how="outer")
)
recon["abs_diff"] = (recon["reported_aum"] - recon["market_value_base"]).abs()
print(f"portfolio-snapshot pairs checked: {len(recon)}")
print(f"largest AUM vs holdings difference: {recon['abs_diff'].max():.4f}")

client_recon = (
    portfolios.groupby("client_id", as_index=False)["aum_usd_current"].sum()
    .merge(clients[["client_id", "total_aum_usd"]], on="client_id")
)
client_recon["abs_diff"] = (client_recon["aum_usd_current"] - client_recon["total_aum_usd"]).abs()
print(f"largest client AUM difference: {client_recon['abs_diff'].max():.4f}")
""")

code("""
# Internal arithmetic: does market_value_local really equal quantity x price_local,
# and does holdings.price_local match the price history in instruments.csv?
mv_gap = (holdings["quantity"] * holdings["price_local"] - holdings["market_value_local"]).abs()
print(f"rows where quantity x price != market_value_local (>0.01): {(mv_gap > 0.01).sum()}")

price_long = instruments.melt(
    id_vars=["instrument_id"],
    value_vars=[f"price_{d}" for d in SNAPSHOTS],
    var_name="col",
    value_name="reference_price",
).assign(snapshot_date=lambda d: d["col"].str.removeprefix("price_"))

price_check = holdings.merge(price_long, on=["instrument_id", "snapshot_date"], how="left")
price_gap = (price_check["price_local"] - price_check["reference_price"]).abs()
print(f"rows where holdings price != instruments price (>0.005): {(price_gap > 0.005).sum()}")

weights = holdings.groupby(["snapshot_date", "portfolio_id"])["weight_pct"].sum()
print(f"portfolio weight sums outside 99.5-100.5: {((weights < 99.5) | (weights > 100.5)).sum()}")
""")

# ---------------------------------------------------------------- 3. time
md("""
## 3. The time dimension

**What we check.** Which snapshots exist for which portfolio, what the whole book was worth at each
date, and which asset classes drove the change. Then we line the moves up against `event_log.csv`,
which is the only authoritative record of what happened in the world in 2026.

**Why it matters.** Clients do not ask what their allocation is; they ask why their portfolio is
down. Answering that needs at least two dated positions and a link to something that actually
happened, which is why the event log is treated as the only authoritative source rather than
letting a model improvise about geopolitics in front of a client. There is also a reporting
obligation hiding here: performance and cash flow are not the same thing, and a rise in account
value that is really a deposit must never be presented as a return. So the pipeline has to be able
to say which part of a change was price, which was currency, and which was money moving.

**What we found.** All 24 portfolios are present at all five snapshots, so there are no gaps to
patch. The book went **USD 577.2m → 596.2m, +3.30%**, but that headline is misleading in two ways
and both matter:

1. **USD 14.7m of the USD 19.0m increase is not performance.** It is six structured-product
   subscriptions and one gold purchase that appear in `holdings` as brand-new positions with no
   offsetting sale or cash reduction. Decomposing the change gives **price +USD 12.6m (+2.19pp),
   FX −USD 8.3m (−1.43pp), new positions +USD 14.7m (+2.54pp)**. **Excluding the new positions the
   book returned +0.76% in USD**, not +3.30%. In local-currency terms — before the dollar's rise is
   translated in — prices added +2.19%.
2. **The book average hides a violent split.** Fixed income fell 7.8% while commodities rose 13.5%
   and equity rose 6.5%. The clients who lost money in 2026 are the conservative ones.

The shape over time matches the event log closely. The book rose 2.74% into 2026-02-27 — the last
business day before the Middle East offensive — then **fell 1.48% into 2026-03-31** as the Strait of
Hormuz closed, Brent went from USD 72 to USD 104 and the VIX went from 17.8 to 31.4. It recovered
from there. Energy and shipping names did the opposite of the book: **Bara Nusantara Energy +35.9%
and Pacific Orient Shipping +26.6% by 31 March alone**, with defence and aerospace +34.0% over the
full period. Long-duration bonds were the persistent drag — the **US Treasury 2.375% of 2045 is down
14.9%** as the 10-year yield moved 4.05% → 4.66% and US CPI went 2.7% → 4.0%. That is ordinary bond
mathematics rather than a credit problem: a long-dated bond loses price when yields rise, and the
longer the maturity the more it loses. It is also the single hardest thing to explain to an income
client, which is why two of the RM notes are about exactly this.

> **Pipeline action.** Stage S4 computes the three-way decomposition per client and per position
> and publishes it as `change_report/<client_id>.json`. **Never expose a single "return" number
> without its decomposition**, and never let the new-position component sit inside a performance
> figure. Attribution must carry the `event_log` row id that supports it, using the existing
> `event_log:<date>:<hash>` evidence key.
""")

code("""
# Every portfolio at every snapshot? A gap here would break all period comparisons.
coverage = (
    holdings.pivot_table(
        index="portfolio_id", columns="snapshot_date", values="instrument_id", aggfunc="count"
    )
    .reindex(columns=SNAPSHOTS)
)
print(f"portfolios: {len(coverage)}   snapshots each: {coverage.notna().sum(axis=1).unique()}")
print(f"positions per snapshot: {holdings.groupby('snapshot_date').size().to_dict()}")
coverage.head(8)
""")

code("""
book = holdings.groupby("snapshot_date")["market_value_usd"].sum().reindex(SNAPSHOTS)
book_table = pd.DataFrame({
    "total_usd_m": (book / 1e6).round(2),
    "change_vs_prev_pct": (book.pct_change() * 100).round(2),
    "change_vs_start_pct": ((book / book.iloc[0] - 1) * 100).round(2),
    "label": market.drop_duplicates("snapshot_date").set_index("snapshot_date")["snapshot_label"],
})
book_table
""")

code("""
fig, ax = plt.subplots()
ax.plot(SNAPSHOTS, book.values / 1e6, marker="o", color="#1f4e79")
for x, y in zip(SNAPSHOTS, book.values / 1e6):
    ax.annotate(f"{y:,.0f}", (x, y), textcoords="offset points", xytext=(0, 9), ha="center")
ax.set_title("Total book value across the five snapshots")
ax.set_xlabel("Snapshot date")
ax.set_ylabel("Total market value (USD millions)")
ax.set_ylim(560, 615)
plt.tight_layout()
plt.show()
""")

code("""
by_class = (
    holdings.pivot_table(
        index="snapshot_date", columns="asset_class", values="market_value_usd", aggfunc="sum"
    )
    .reindex(index=SNAPSHOTS, columns=ASSET_CLASSES)
)

summary = pd.DataFrame({
    "usd_m_start": (by_class.loc[FIRST] / 1e6).round(1),
    "usd_m_end": (by_class.loc[LAST] / 1e6).round(1),
    "change_pct": ((by_class.loc[LAST] / by_class.loc[FIRST] - 1) * 100).round(1),
})
display(summary)

# Structured Products is left off the chart: its +432% is six new subscriptions, not a price move,
# and plotting it flattens every other series into an unreadable band. Its numbers are in the
# table above, and section 11 explains why it grew.
priced_classes = [c for c in ASSET_CLASSES if c != "Structured Products"]
indexed = by_class / by_class.loc[FIRST] * 100

fig, ax = plt.subplots()
for column in priced_classes:
    ax.plot(SNAPSHOTS, indexed[column], marker="o", label=column)
ax.axhline(100, color="black", linewidth=0.8)
ax.axvline("2026-03-31", color="#c0392b", linestyle="--", linewidth=1)
ax.annotate(
    "Strait closed 4 March",
    xy=("2026-03-31", 1.0),
    xycoords=("data", "axes fraction"),
    xytext=(0, -12),
    textcoords="offset points",
    fontsize=8,
    color="#c0392b",
    ha="center",
)
ax.set_title("Asset class value over time, excluding Structured Products (2025-12-31 = 100)")
ax.set_xlabel("Snapshot date")
ax.set_ylabel("Value indexed to 100 at 2025-12-31")
ax.legend(fontsize=8, loc="lower left")
plt.tight_layout()
plt.show()
print("Structured Products is off this chart: its +432% is six new subscriptions, not a price move.")
""")

code("""
# Split the book's change into price, FX and new-position effects.
def client_instrument_snapshot(date):
    frame = holdings[holdings["snapshot_date"] == date]
    grouped = frame.groupby(["client_id", "instrument_id"]).agg(
        qty=("quantity", "sum"),
        px=("price_local", "first"),
        mv_usd=("market_value_usd", "sum"),
        mv_local=("market_value_local", "sum"),
    )
    grouped["usd_per_local"] = grouped["mv_usd"] / grouped["mv_local"]
    return grouped


start, end = client_instrument_snapshot(FIRST), client_instrument_snapshot(LAST)
joined = start.join(end, lsuffix="_s", rsuffix="_e", how="outer")
joined["usd_per_local_s"] = joined["usd_per_local_s"].fillna(joined["usd_per_local_e"])
joined["usd_per_local_e"] = joined["usd_per_local_e"].fillna(joined["usd_per_local_s"])
joined["px_s"] = joined["px_s"].fillna(joined["px_e"])
joined["px_e"] = joined["px_e"].fillna(joined["px_s"])
joined[["qty_s", "qty_e", "mv_usd_s", "mv_usd_e"]] = joined[
    ["qty_s", "qty_e", "mv_usd_s", "mv_usd_e"]
].fillna(0)

joined["price_effect"] = joined["qty_s"] * (joined["px_e"] - joined["px_s"]) * joined["usd_per_local_s"]
joined["fx_effect"] = joined["qty_s"] * joined["px_e"] * (joined["usd_per_local_e"] - joined["usd_per_local_s"])
joined["new_position_effect"] = (joined["qty_e"] - joined["qty_s"]) * joined["px_e"] * joined["usd_per_local_e"]
joined["total"] = joined["mv_usd_e"] - joined["mv_usd_s"]

effects = joined[["price_effect", "fx_effect", "new_position_effect", "total"]].sum()
contribution = effects / book.loc[FIRST] * 100

print("Book change 2025-12-31 -> 2026-08-26")
print(
    pd.DataFrame({
        "usd_m": (effects / 1e6).round(2),
        "contribution_pp": contribution.round(2),
    }).to_string()
)
print(f"\\nunexplained residual: {(effects[:3].sum() - effects['total']):.2f} USD")
print(
    f"\\nExcluding the unfunded new positions, the book returned "
    f"{contribution['price_effect'] + contribution['fx_effect']:+.2f}% in USD "
    f"({contribution['price_effect']:+.2f} from prices, {contribution['fx_effect']:+.2f} from the dollar)."
)
DECOMPOSITION = joined  # reused in section 4
""")

code("""
# The authoritative 2026 event record. Everything we say about causes must trace back to a row here.
events[["event_date", "event_type", "region", "severity", "primary_transmission"]]
""")

code("""
# The market backdrop at the same five dates, so moves can be tied to levels.
key_series = ["BRENT_USD_BBL", "GOLD_USD_OZ", "UST_10Y_PCT", "VIX", "SPX", "US_CPI_YOY_PCT"]
market[market["series_id"].isin(key_series)].pivot_table(
    index="series_id", columns="snapshot_date", values="value"
).reindex(index=key_series, columns=SNAPSHOTS)
""")

code("""
# Which instruments actually moved, and in which direction.
prices = instruments.set_index("instrument_id")[[f"price_{d}" for d in SNAPSHOTS]]
moves = pd.DataFrame({
    "instrument_name": instruments.set_index("instrument_id")["instrument_name"],
    "sector": instruments.set_index("instrument_id")["sector"],
    "to_31_mar_pct": (prices[f"price_{SNAPSHOTS[2]}"] / prices[f"price_{FIRST}"] - 1) * 100,
    "full_period_pct": (prices[f"price_{LAST}"] / prices[f"price_{FIRST}"] - 1) * 100,
}).round(1)

print("BIGGEST FALLERS")
display(moves.sort_values("full_period_pct").head(7))
print("BIGGEST RISERS")
display(moves.sort_values("full_period_pct").tail(7).iloc[::-1])
""")

# ---------------------------------------------------------------- 4. drift
md("""
## 4. Per-client allocation and drift

**What we check.** Asset-class allocation for each **household** (all of a client's portfolios added
together) at every snapshot, and how much each allocation moved between the first and last snapshot.
We also measure each client's return in their **own base currency**, not USD.

**Why it matters.** A bank owes its suitability assessment on the whole relationship, not on each
account separately, so a client's real risk is the sum of their portfolios. Reporting currency
matters just as much: a European client who earns, spends and pays tax in euros has not lost money
because the dollar rose, and telling them otherwise damages trust for no reason. Drift also carries
a governance meaning. Allocation that moved because markets moved is the bank's problem to correct;
allocation that moved because the client instructed a trade is the client's decision, and the two
belong in different queues with different paperwork.

**What we found.** Two findings, and the second is the one to build on.

**Currency of measurement changes the answer, and by a lot.** Andreas Lindqvist (CL-0009) is
**−4.0% in USD but +2.0% in EUR**. Margarethe Voss-Brenner is **−5.7% in USD but +0.2% in EUR** —
the difference between "you lost money" and "you broke even". Tan Boon Huat is −6.7% in USD but
−2.3% in SGD. The US dollar rose against every currency in the book (EURUSD 1.160 → 1.092, USDSGD
1.290 → 1.352, USDJPY 152 → 159), costing the USD-reported book **USD 8.3m that no client actually
lost**. Every non-USD client shows a gap of 4.5 to 6.0 percentage points. **The pipeline must report
client performance in the client's own base currency.**

**Risk profile and outcome are inverted this year.** Measured in base currency, the two worst
performers in the book are the **two Income clients** — Cheung Kwok Wing −7.0% and Chalermchai
Suphanburi −6.6% — followed by Lau Chi Ming −5.8% (HKD), Tan Boon Huat −2.3% (SGD) and Nguyen Thi
Bao Tran −1.6% (SGD). Neither Conservative client made money: Tan Boon Huat −2.3%, Margarethe
Voss-Brenner +0.2%. The four best are the aggressive ones: Abdullah Al-Mansoori +25.9%, Kim Do-Yoon
+25.3%, Hartono Wijaya Kusuma +23.4% (SGD) and Zhang Meiling +18.6%. **The clients who were told
bonds are the safe part are the clients who lost money**, which is exactly the conversation
Priscilla has to have (RM notes N-007, N-016, N-028).

The largest allocation drifts are all the new structured-product notes appearing from nothing:
Abdullah Al-Mansoori 0 → 12.9%, Kim Do-Yoon 0 → 12.8%, Zhang Meiling 0 → 7.1%, Lau Chi Ming
0 → 7.1%. Every one has a matching `Structured Product Subscription` transaction whose narrative
says the client asked for it, so these are **client-directed**, not passive drift — a different
governance category even though the arithmetic is identical.

> **Pipeline action.** Compute allocation at **household level in the client's base currency**, and
> publish both `return_base_ccy_pct` and `return_usd_pct` in `curated_client_bundle` — never one
> without the other. Tag each drift row `client_directed` when a transaction for that instrument
> exists inside the period and `market_drift` otherwise. That flag decides whether the RM sees a
> rebalancing prompt or a suitability review prompt.
""")

code("""
household = (
    holdings.groupby(["client_id", "snapshot_date", "asset_class"], as_index=False)["market_value_usd"]
    .sum()
)
household_total = (
    holdings.groupby(["client_id", "snapshot_date"], as_index=False)["market_value_usd"]
    .sum()
    .rename(columns={"market_value_usd": "household_total_usd"})
)
household = household.merge(household_total, on=["client_id", "snapshot_date"])
household["pct"] = household["market_value_usd"] / household["household_total_usd"] * 100

allocation = household.pivot_table(
    index=["client_id", "asset_class"], columns="snapshot_date", values="pct"
).reindex(columns=SNAPSHOTS).fillna(0.0)
allocation["drift_pp"] = allocation[LAST] - allocation[FIRST]
allocation = allocation.reset_index()
allocation.insert(1, "client_name", allocation["client_id"].map(NAME))

top_drift = allocation.reindex(allocation["drift_pp"].abs().sort_values(ascending=False).index).head(12)
top_drift[["client_id", "client_name", "asset_class", FIRST, LAST, "drift_pp"]].round(2)
""")

code("""
labels = [f"{r.client_name} — {r.asset_class}" for r in top_drift.head(10).itertuples()]
values = top_drift.head(10)["drift_pp"].to_numpy()

fig, ax = plt.subplots(figsize=(11, 5.5))
ax.barh(labels[::-1], values[::-1], color=["#c0392b" if v > 0 else "#1f4e79" for v in values[::-1]])
ax.axvline(0, color="black", linewidth=0.8)
ax.set_title("Largest household allocation drifts, 2025-12-31 to 2026-08-26")
ax.set_xlabel("Change in allocation (percentage points)")
ax.set_ylabel("")
plt.tight_layout()
plt.show()
""")

code("""
# Return in USD versus return in the client's own base currency.
base_totals = (
    holdings.groupby(["client_id", "snapshot_date"])["market_value_base"].sum().unstack("snapshot_date")
).reindex(columns=SNAPSHOTS)
usd_totals = (
    holdings.groupby(["client_id", "snapshot_date"])["market_value_usd"].sum().unstack("snapshot_date")
).reindex(columns=SNAPSHOTS)

performance = pd.DataFrame({
    "client_name": pd.Series(NAME),
    "base_ccy": pd.Series(BASE_CCY),
    "risk_profile": clients.set_index("client_id")["risk_profile"],
    "usd_m_now": (usd_totals[LAST] / 1e6).round(1),
    "return_usd_pct": ((usd_totals[LAST] / usd_totals[FIRST] - 1) * 100).round(2),
    "return_base_ccy_pct": ((base_totals[LAST] / base_totals[FIRST] - 1) * 100).round(2),
})
performance["fx_gap_pp"] = (performance["return_usd_pct"] - performance["return_base_ccy_pct"]).round(2)
performance.sort_values("return_base_ccy_pct")
""")

code("""
ordered = performance.sort_values("return_base_ccy_pct")
labels = [f"{n} ({p})" for n, p in zip(ordered["client_name"], ordered["risk_profile"])]

fig, ax = plt.subplots(figsize=(11, 7))
ax.barh(labels, ordered["return_base_ccy_pct"],
        color=["#c0392b" if v < 0 else "#1f7a3f" for v in ordered["return_base_ccy_pct"]])
ax.axvline(0, color="black", linewidth=0.8)
ax.set_title("Return in the client's own base currency, 2025-12-31 to 2026-08-26")
ax.set_xlabel("Return (%)")
ax.set_ylabel("Client (risk profile)")
plt.tight_layout()
plt.show()
""")

# ---------------------------------------------------------------- 5. mandates
md("""
## 5. Mandate compliance

**What we check.** Every managed portfolio's allocation at the latest snapshot against the
`min_pct` / `max_pct` bands in `mandates.csv`, plus the single-position limit. Custody accounts are
excluded because the bank does not manage them and they are not measured against a mandate.

**Why it matters.** The mandate bands are the contract. Under the suitability regimes these
booking centres work to — MiFID II style rules in Europe, the FinSA/FINMA framework in Switzerland,
and the MAS conduct rules in Singapore — a bank that manages money against a stated risk profile
must be able to show the portfolio actually matches that profile, and must document any deviation.
A Conservative client sitting at 71% equity is not merely off-target; it is evidence that the
assessed risk profile and the risk actually being run have come apart. That is a compliance
exposure today and, if markets fall, a complaint the bank would struggle to defend. The operational
distinction is drift versus client-directed: drift is the bank's to correct, while a documented
instruction with a signed waiver on file is a different conversation entirely.

**What we found.** **14 band breaches across 9 of the 20 clients** at 2026-08-26. Ranked by gap:

| Client | Mandate | Asset class | Actual | Limit | Gap |
|---|---|---|---|---|---|
| Margarethe Voss-Brenner | Conservative | Equity | 71.46% | max 30% | **+41.5pp** |
| Margarethe Voss-Brenner | Conservative | Fixed Income | 9.15% | min 45% | −35.9pp |
| Tan Boon Huat | Conservative | Alternatives | 47.28% | max 15% | +32.3pp |
| Andreas Lindqvist | Balanced | Cash | 44.98% | max 18% | +27.0pp |
| Tan Boon Huat | Conservative | Fixed Income | 24.47% | min 45% | −20.5pp |
| Aishah binti Rahman | Sustainable Balanced | Equity | 67.74% | max 55% | +12.7pp |
| Yamamoto Kenji | Balanced | Equity | 67.72% | max 55% | +12.7pp |

**The golden number is confirmed exactly.** Margarethe Voss-Brenner (CL-0003) holds
**71.46% equity against a Conservative mandate that caps equity at 30%** — a 41.5 point breach, the
largest in the book — while her fixed income sits at 9.15% against a 45% floor. Her nine source
rows are printed below. Her risk tolerance score is 2 out of 10.

Three breaches have a stated cause in the RM notes and should be labelled differently from drift:
Alistair Pemberton-Hale's commodities overweight (18.93% vs 10% max) has a **signed suitability
waiver on file** (note N-010); Andreas Lindqvist's 45% cash is a client who agreed a deployment plan
twice and never executed it (N-013); Margarethe's breach is an **inherited portfolio the client
asked us not to change** (N-005).

Separately, the Sustainable Balanced mandate carries binding exclusions, and **Aishah binti Rahman
holds 21.3% of her sustainable mandate in instruments flagged `sustainability_excluded = Y`** —
Global Energy Majors (11.13%) and Sunrise Palm Resources (10.17%). Note N-008 records that she
believes the portfolio is fully aligned and was unaware of the energy fund. An exclusion breach is
stricter than a band breach: a band can be drifted through legitimately, whereas an exclusion is
binary and the mandate documentation says it is binding.

> **Pipeline action.** Two separate rules in stage S5. **`mandate_band_breach`** tests allocation
> against `min_pct`/`max_pct` per managed portfolio, filtering out `service_model == "Custody"`.
> **`mandate_exclusion_breach`** tests `sustainability_excluded == "Y"` against the mandate's
> exclusion list and is always severity `high`, never "drift". Every emitted breach carries the
> `mandates:<mandate_code>:<asset-class-slug>` evidence id plus the contributing
> `holdings:<snapshot>:<portfolio>:<instrument>` ids, and a `waiver_note_id` field populated from
> the RM notes when one exists — an alert that cannot see the waiver is a wrong alert.
""")

code("""
latest = holdings[holdings["snapshot_date"] == TODAY]

portfolio_alloc = latest.groupby(["portfolio_id", "asset_class"], as_index=False)["market_value_base"].sum()
portfolio_total = (
    latest.groupby("portfolio_id", as_index=False)["market_value_base"].sum()
    .rename(columns={"market_value_base": "portfolio_total"})
)
portfolio_alloc = portfolio_alloc.merge(portfolio_total, on="portfolio_id")
portfolio_alloc["actual_pct"] = portfolio_alloc["market_value_base"] / portfolio_alloc["portfolio_total"] * 100

portfolio_alloc = (
    portfolio_alloc
    .merge(portfolios[["portfolio_id", "client_id", "mandate_code", "service_model"]], on="portfolio_id")
    .merge(mandates[["mandate_code", "asset_class", "min_pct", "target_pct", "max_pct"]],
           on=["mandate_code", "asset_class"], how="left")
)
portfolio_alloc["client_name"] = portfolio_alloc["client_id"].map(NAME)

managed = portfolio_alloc[portfolio_alloc["service_model"] != "Custody"].copy()
managed["over_max_pp"] = (managed["actual_pct"] - managed["max_pct"]).clip(lower=0)
managed["under_min_pp"] = (managed["actual_pct"] - managed["min_pct"]).clip(upper=0)
managed["gap_pp"] = managed["over_max_pp"] + managed["under_min_pp"]

breaches = managed[managed["gap_pp"] != 0].copy()
breaches["direction"] = np.where(breaches["gap_pp"] > 0, "above max", "below min")
breaches = breaches.reindex(breaches["gap_pp"].abs().sort_values(ascending=False).index)

print(f"band breaches at {TODAY}: {len(breaches)} across {breaches['client_id'].nunique()} clients")
print(f"custody portfolios excluded: {(portfolios['service_model'] == 'Custody').sum()}")
breaches[["client_id", "client_name", "portfolio_id", "mandate_code", "asset_class",
          "actual_pct", "min_pct", "max_pct", "gap_pp", "direction"]].round(2)
""")

code("""
top_breaches = breaches.head(10).iloc[::-1]
labels = [f"{r.client_name} — {r.asset_class}" for r in top_breaches.itertuples()]

fig, ax = plt.subplots(figsize=(11.5, 5.5))
ax.barh(labels, top_breaches["gap_pp"],
        color=["#c0392b" if v > 0 else "#e08214" for v in top_breaches["gap_pp"]])
ax.axvline(0, color="black", linewidth=0.8)
ax.set_title(f"Mandate band breaches at {TODAY} (positive = above max, negative = below min)")
ax.set_xlabel("Distance outside the band (percentage points)")
ax.set_ylabel("")
plt.tight_layout()
plt.show()
""")

code("""
# GOLDEN NUMBER 1 — Margarethe Voss-Brenner, CL-0003. Source rows, unaggregated.
mv = latest[latest["client_id"] == "CL-0003"]
display(
    mv[["portfolio_id", "instrument_id", "instrument_name", "asset_class", "instrument_ccy",
        "quantity", "price_local", "market_value_base", "weight_pct", "liquidity_tier"]]
    .sort_values("market_value_base", ascending=False)
)

total_eur = mv["market_value_base"].sum()
equity_eur = mv.loc[mv["asset_class"] == "Equity", "market_value_base"].sum()
cons_equity_max = mandates.loc[
    (mandates["mandate_code"] == "CONS") & (mandates["asset_class"] == "Equity"), "max_pct"
].item()

print(f"portfolio           : PF-0005, mandate CONS (Conservative), Advisory")
print(f"total (EUR)         : {total_eur:,.2f}")
print(f"equity (EUR)        : {equity_eur:,.2f}")
print(f"equity share        : {equity_eur / total_eur * 100:.2f}%")
print(f"mandate equity max  : {cons_equity_max:.0f}%")
print(f"breach              : {equity_eur / total_eur * 100 - cons_equity_max:.2f} percentage points")
print(f"client risk profile : {clients.set_index('client_id').loc['CL-0003', 'risk_profile']}"
      f" (tolerance {clients.set_index('client_id').loc['CL-0003', 'risk_tolerance_score']}/10)")
""")

code("""
# Sustainable Balanced carries binding exclusions. Are they respected?
excl = (
    latest.merge(instruments[["instrument_id", "sustainability_excluded"]], on="instrument_id")
    .merge(portfolios[["portfolio_id", "mandate_code"]], on="portfolio_id")
)
susbal_breach = excl[(excl["mandate_code"] == "SUSBAL") & (excl["sustainability_excluded"] == "Y")]
susbal_breach = susbal_breach.assign(client_name=lambda d: d["client_id"].map(NAME))

print("Excluded instruments held inside a Sustainable Balanced mandate:")
display(
    susbal_breach[["client_id", "client_name", "portfolio_id", "instrument_name",
                   "market_value_base", "weight_pct"]].round(2)
)
print(f"total excluded weight in that mandate: {susbal_breach['weight_pct'].sum():.2f}%")
""")

# ---------------------------------------------------------------- 6. look-through
md("""
## 6. Look-through and concentration

**What we check.** Two kinds of risk that are invisible on a standard position report.

1. **Multi-portfolio aggregation.** A position that is 100% of a small custody account is only 41%
   of the household — but the reverse is what matters: a position that looks modest in one portfolio
   can dominate the household.
2. **Look-through.** `instruments.underlying_reference` says what a structured product is actually
   exposed to. Its `asset_class` only says what it is called. We also group instruments by
   **issuer**, so shares, a perpetual bond and an accumulator on the same company count as one bet.

**Method note.** All six structured products here are *worst-of* notes: the payoff is driven by
whichever named underlying performs worst. For risk purposes we therefore attribute the **full
notional to every named underlying**, and we say so — this is deliberately conservative and any
number we publish must carry that caveat.

**Why it matters.** Concentration limits exist because single-name risk is what actually destroys
private wealth — not volatility, but one position going to zero. Two things defeat a standard
position report. First, a structured product is booked as one line carrying the issuing bank's
name, but economically you own whatever sits in the basket; a worst-of note behaves much more like
selling insurance on every name in it than like holding a bond. Second, a client's shares, their
bonds and their derivatives on the same company are three lines on the statement and one bet in
reality — and if the issuer fails, all three fail together. Add household aggregation across
accounts and the true number can be double what any single report shows.

**What we found.** Four clients whose real single-issuer concentration only appears after this
treatment, and — more striking — **two clients who carry double-digit exposure to a company they do
not hold a single share of**.

| Client | Held directly | Via structured products | Look-through total | Single-position limit |
|---|---|---|---|---|
| Hartono Wijaya Kusuma (CL-0001) — Bara Nusantara Energy | 41.4% | 3.6% | **45.0%** | 15% |
| Lau Chi Ming (CL-0014) — Golden Harbour Properties | 22.4% (9.5% shares + 12.9% perpetual) | 7.1% accumulator | **29.5%** | 12% |
| Abdullah Al-Mansoori (CL-0019) — Pacific Orient Shipping | 11.4% | 12.9% | **24.3%** | 15% |
| Zhang Meiling (CL-0013) — Helios Cloud Systems | 15.4% | 7.1% | **22.5%** | 15% |
| **Abdullah Al-Mansoori — Bara Nusantara Energy** | **0.0%** | 12.9% | **12.9%** | 15% |
| **Kim Do-Yoon (CL-0015) — Helios Cloud Systems** | **0.0%** | 12.8% | **12.8%** | 20% |

**Lau Chi Ming is the strongest case in the book.** Three separate instruments — ordinary shares, a
perpetual bond and an accumulator — are one bet on one Hong Kong property company, and none of them
looks alarming on its own. Add the Mid-Levels apartment and Hong Kong property is **49% of his
household**. Every one of those instruments fell: accumulator −41.7%, perpetual −31.1%, shares
−24.2% — the three worst performers in the entire instrument universe. RM note N-018 records the RM
telling him "the perpetual, the shares, the accumulator and his own development business are all the
same bet" and the client answering "that is why he is confident".

**The zero-direct-holding cases are the ones a standard report can never surface.** Abdullah
Al-Mansoori's worst-of note names an Indonesian coal miner in its basket, so 12.9% of his wealth
moves with a stock that appears nowhere on his statement. Kim Do-Yoon is in the same position on a
US software company. There is no line item to click on.

Two more concentration facts worth carrying forward. Ravi Chandrasekaran (CL-0002) has **68.4% of
his household in one unlisted pre-IPO holding** that sits in a Custody account and is therefore
measured against no mandate at all — and that holding is also the stale valuation from section 11.
And Nordvind Industrial AB is held by two unrelated clients (CL-0003 at 18.4%, CL-0009 at 17.2%), so
one single-name shock hits two households at once.

> **Pipeline action.** Stage S3 builds two static reference maps that live in version control, not
> in code comments: `lookthrough_map` (structured product id → list of underlying instrument ids,
> derived by reading `instruments.underlying_reference`) and `issuer_map` (instrument id → issuer
> key, grouping shares, bonds and derivatives on one company). Stage S4 then computes
> `issuer_exposure_pct` at household level as direct holdings plus the **full notional** of every
> note referencing that issuer. Publish `direct_pct` and `lookthrough_pct` as separate fields with
> an explicit `attribution_basis: "worst_of_full_notional"` marker, so the conservative assumption
> travels with the number and any consumer can see it.
""")

code("""
# Which structured products exist, what they really reference, and who holds them.
lookthrough_source = instruments.loc[
    instruments["underlying_reference"].notna(),
    ["instrument_id", "instrument_name", "asset_class", "liquidity_tier", "underlying_reference"],
]
lookthrough_source
""")

code("""
# Read by hand from underlying_reference above. Worst-of => full notional to each named underlying.
LOOKTHROUGH = {
    "SYN-SP-0501": ["SYN-EQ-0008", "SYN-ST-0103"],   # energy majors + Helios (Gulf Marine not in universe)
    "SYN-SP-0502": ["SYN-ST-0103"],                   # Helios Cloud Systems, single underlying
    "SYN-SP-0503": ["SYN-ST-0106"],                   # Golden Harbour Properties accumulator
    "SYN-SP-0504": ["SYN-CM-0401"],                   # gold spot
    "SYN-SP-0505": ["SYN-ST-0104", "SYN-EQ-0008", "SYN-ST-0101"],  # shipping + energy + coal
    "SYN-SP-0506": [],                                # three Asian banks, not in the instrument universe
}

# Same-issuer grouping: different instruments, one credit/equity story.
ISSUER = {
    "SYN-ST-0106": "Golden Harbour Properties",
    "SYN-FI-0207": "Golden Harbour Properties",
    "SYN-SP-0503": "Golden Harbour Properties",
    "SYN-ST-0103": "Helios Cloud Systems",
    "SYN-SP-0502": "Helios Cloud Systems",
    "SYN-ST-0101": "Bara Nusantara Energy",
    "SYN-ST-0104": "Pacific Orient Shipping",
}

household_totals = latest.groupby("client_id")["market_value_usd"].sum()


def exposure_pct(client_id, instrument_ids):
    frame = latest[(latest["client_id"] == client_id) & (latest["instrument_id"].isin(instrument_ids))]
    return frame["market_value_usd"].sum() / household_totals[client_id] * 100


rows = []
for client_id in sorted(latest["client_id"].unique()):
    for issuer in sorted(set(ISSUER.values())):
        # instruments issued by this company, split into cash instruments and notes on it
        members = [i for i, name in ISSUER.items() if name == issuer]
        cash_instruments = [i for i in members if i not in LOOKTHROUGH]
        own_notes = [i for i in members if i in LOOKTHROUGH]
        # notes issued by anyone else whose underlying basket names this issuer
        referencing = [
            note for note, underlyings in LOOKTHROUGH.items()
            if note not in members and any(ISSUER.get(u) == issuer for u in underlyings)
        ]
        direct_pct = exposure_pct(client_id, cash_instruments)
        note_pct = exposure_pct(client_id, own_notes + referencing)
        if direct_pct + note_pct > 0:
            rows.append({
                "client_id": client_id,
                "client_name": NAME[client_id],
                "issuer": issuer,
                "direct_pct": direct_pct,
                "via_structured_product_pct": note_pct,
                "lookthrough_pct": direct_pct + note_pct,
            })

lookthrough = pd.DataFrame(rows)
lookthrough["uplift_pp"] = lookthrough["lookthrough_pct"] - lookthrough["direct_pct"]
lookthrough.sort_values("lookthrough_pct", ascending=False).round(2)
""")

code("""
hidden = lookthrough[lookthrough["uplift_pp"] > 0].sort_values("lookthrough_pct")
labels = [f"{r.client_name} — {r.issuer}" for r in hidden.itertuples()]
y = np.arange(len(hidden))

fig, ax = plt.subplots(figsize=(10.5, 5.5))
ax.barh(y + 0.2, hidden["direct_pct"], 0.4, label="Held directly (shown on the report)", color="#9fb8d4")
ax.barh(y - 0.2, hidden["lookthrough_pct"], 0.4, label="After look-through and issuer grouping", color="#c0392b")
ax.set_yticks(y, labels, fontsize=8)
ax.set_title("Single-issuer exposure, before and after look-through")
ax.set_xlabel("Share of household wealth (%)")
ax.set_ylabel("")
ax.legend(loc="lower right")
plt.tight_layout()
plt.show()
""")

code("""
# Single-position limits measured at household level, for instruments the limit is meant to apply to.
position_pct = (
    latest.merge(instruments[["instrument_id", "concentration_limit_applies"]], on="instrument_id")
    .groupby(["client_id", "instrument_id", "instrument_name", "concentration_limit_applies"], as_index=False)
    ["market_value_usd"].sum()
)
position_pct["household_pct"] = (
    position_pct["market_value_usd"] / position_pct["client_id"].map(household_totals) * 100
)
position_pct["client_name"] = position_pct["client_id"].map(NAME)

limits = (
    portfolios.merge(mandates[["mandate_code", "max_single_position_pct"]].drop_duplicates(), on="mandate_code")
    .groupby("client_id")["max_single_position_pct"].min()
)
position_pct["household_limit_pct"] = position_pct["client_id"].map(limits)

flagged = position_pct[
    (position_pct["concentration_limit_applies"] == "Y")
    & (position_pct["household_pct"] > position_pct["household_limit_pct"])
].sort_values("household_pct", ascending=False)

print("Single positions above the tightest single-position limit in the household:")
print("Caveat: the limit binds per managed portfolio. Measured at household level it is a risk")
print("signal, not a compliance finding — CL-0002's 68.4% sits in a Custody account.")
flagged[["client_id", "client_name", "instrument_name", "market_value_usd",
         "household_pct", "household_limit_pct"]].round(2)
""")

code("""
# The two clearest aggregation cases, shown from source rows.
for client_id in ["CL-0002", "CL-0014"]:
    frame = latest[latest["client_id"] == client_id].copy()
    frame["household_pct"] = frame["market_value_usd"] / frame["market_value_usd"].sum() * 100
    print(f"{client_id} — {NAME[client_id]}   household USD {frame['market_value_usd'].sum():,.0f}")
    display(
        frame[["portfolio_id", "instrument_name", "asset_class", "weight_pct", "household_pct"]]
        .sort_values("household_pct", ascending=False).round(2)
    )
""")

# ---------------------------------------------------------------- 7. liquidity
md("""
## 7. Liquidity versus cash needs

**What we check.** For each client we compare what they have to pay in the next twelve months —
`planned_cash_needs.csv` plus uncalled private-market `commitments.csv` — against what they can
actually raise. We define three tiers from `holdings.liquidity_tier`:

- **Cash** — the `Cash and Equivalents` asset class.
- **Sellable in days** — anything with `liquidity_tier = Daily`.
- **Locked** — `Weekly`, `Monthly`, `Quarterly Gate` and `Illiquid`.

**Why it matters.** Liquidity in private banking is a tiering question, not a yes-or-no. Cash is
available today; listed funds and shares settle a couple of days after you sell; hedge funds
typically redeem monthly with notice; semi-liquid private credit vehicles deal quarterly and the
manager can pull a **gate** that limits how much of your redemption is actually met; private equity
cannot be sold at all and, worse, **calls** money from you on its own schedule. So a client can be
extremely wealthy and still unable to meet a dated bill. Forcing a sale into a bad market to hit a
tax deadline is precisely the outcome an advisory relationship exists to prevent — a dated
liability should be funded from assets deliberately matched to it, not from whatever happens to be
easiest to sell that week.

**What we found.** Across the book, USD 442.9m of the USD 596.2m is Daily; USD 87.9m is Illiquid and
USD 20.1m sits behind a quarterly gate. **No client is insolvent, but nine of the twenty cannot meet
their twelve-month obligations from cash and must sell something to pay.**

Ranked by cash cover (cash ÷ obligations): Alistair Pemberton-Hale 0.13x, Ravi Chandrasekaran 0.16x,
Fong Enterprises 0.17x, Nguyen Thi Bao Tran 0.19x, Grace Adeyemi-Lim 0.19x, Lau Chi Ming 0.20x,
Hartono Wijaya Kusuma 0.26x, Margarethe Voss-Brenner 0.46x, Abdullah Al-Mansoori 0.48x. Selling is
not itself a problem — but for three of them the assets are locked (Ravi Chandrasekaran has 72% of
his wealth in illiquid or gated holdings, Lau Chi Ming 57%, Tan Boon Huat 54%).

**Golden number 2 is confirmed.** Margarethe Voss-Brenner has a **confirmed EUR 3.4m German
inheritance-tax instalment due between 1 Oct and 31 Dec 2026** — inside four months. Her cash is
**EUR 1.56m, which covers 0.46x of it**. She has EUR 17.9m of Daily-liquid assets, so she can pay;
but funding it means selling, and what she would sell is the equity that is already 41 points
outside her mandate. **Her liquidity problem and her compliance problem have the same solution**,
which is the single most useful sentence in this notebook.

Two liquidity situations are worse in kind, not just degree:

- **Nguyen Thi Bao Tran (CL-0006)** needs USD 11.0m (US tuition plus PE capital calls). She
  submitted a full redemption on Orchard Private Credit Fund II in May; **the manager gated it and
  met roughly 22% of the request** (TXN-0008), and note N-023 records the fund has now gated three
  consecutive quarters. Her SGD assets fund USD obligations, and USDSGD moved from 1.290 to 1.352.
- **Lau Chi Ming (CL-0014)** owes an HKD 60m (USD 7.7m) redevelopment contribution by mid-2027
  against USD 1.5m of cash, and his Lombard facility is at 69.4% LTV against a 70% trigger — so
  selling collateral to raise the cash shrinks the lending value behind a facility that is already
  almost breached. Liquidity and collateral cannot be solved independently for this client.

> **Pipeline action.** Stage S3 maps `liquidity_tier` onto a settlement horizon in days
> (`Daily → 2`, `Weekly → 7`, `Monthly → 30`, `Quarterly Gate → 90` with a `gated: true` flag,
> `Illiquid → null`). Stage S4 computes `liquid_by_horizon` buckets and matches each
> `planned_cash_needs` row to the earliest bucket that settles before `due_from`, weighting by
> `certainty` (`Confirmed` = 1.0, `Likely` = 0.7, `Conditional`/`Aspirational` = 0.3 for the warn
> threshold, and 1.0 for the stress case). Uncalled `commitments` are treated as a liability that
> can be called at any time inside its `expected_call_window`, not as an asset. Gated positions
> must **never** count toward funding a dated need — CL-0006 is the proof.
""")

code("""
LOCKED_TIERS = ["Weekly", "Monthly", "Quarterly Gate", "Illiquid"]
HORIZON_END = "2027-08-26"  # twelve months from today

print("Book-wide liquidity mix at " + TODAY + " (USD millions)")
display((latest.groupby("liquidity_tier")["market_value_usd"].sum() / 1e6).round(1).sort_values(ascending=False))

cash_now = latest[latest["asset_class"] == "Cash and Equivalents"].groupby("client_id")["market_value_usd"].sum()
daily_now = latest[latest["liquidity_tier"] == "Daily"].groupby("client_id")["market_value_usd"].sum()
locked_now = latest[latest["liquidity_tier"].isin(LOCKED_TIERS)].groupby("client_id")["market_value_usd"].sum()

needs = cash_needs.copy()
needs["amount_usd"] = [to_usd(a, c) for a, c in zip(needs["amount"], needs["currency"])]
needs_12m = needs.loc[needs["due_from"] <= HORIZON_END].groupby("client_id")["amount_usd"].sum()

calls = commitments.copy()
calls["uncalled_usd"] = [to_usd(a, c) for a, c in zip(calls["uncalled"], calls["currency"])]
uncalled = calls.groupby("client_id")["uncalled_usd"].sum()

liquidity = pd.DataFrame({
    "client_name": pd.Series(NAME),
    "total_usd": household_totals,
    "cash_usd": cash_now,
    "daily_usd": daily_now,
    "locked_usd": locked_now,
    "needs_12m_usd": needs_12m,
    "uncalled_usd": uncalled,
}).fillna(0.0)
liquidity["obligations_usd"] = liquidity["needs_12m_usd"] + liquidity["uncalled_usd"]
liquidity["cash_cover_x"] = (liquidity["cash_usd"] / liquidity["obligations_usd"].replace(0, np.nan)).round(2)
liquidity["daily_cover_x"] = (liquidity["daily_usd"] / liquidity["obligations_usd"].replace(0, np.nan)).round(2)
liquidity["locked_pct"] = (liquidity["locked_usd"] / liquidity["total_usd"] * 100).round(1)

money = ["total_usd", "cash_usd", "daily_usd", "needs_12m_usd", "uncalled_usd", "obligations_usd"]
liquidity_view = liquidity.sort_values("cash_cover_x")[
    ["client_name", *money, "cash_cover_x", "daily_cover_x", "locked_pct"]
].copy()
liquidity_view[money] = (liquidity_view[money] / 1e6).round(2)
liquidity_view = liquidity_view.rename(columns={c: c.replace("_usd", "_usd_m") for c in money})
liquidity_view
""")

code("""
at_risk = liquidity[liquidity["obligations_usd"] > 0].sort_values("obligations_usd", ascending=False).head(10)
labels = list(at_risk["client_name"])
x = np.arange(len(at_risk))

fig, ax = plt.subplots(figsize=(10.5, 5.5))
ax.bar(x - 0.27, at_risk["obligations_usd"] / 1e6, 0.27, label="Obligations, next 12 months", color="#c0392b")
ax.bar(x, at_risk["cash_usd"] / 1e6, 0.27, label="Cash", color="#1f7a3f")
ax.bar(x + 0.27, at_risk["daily_usd"] / 1e6, 0.27, label="Sellable in days", color="#9fb8d4")
ax.set_xticks(x, labels, rotation=35, ha="right", fontsize=8)
ax.set_title("Known obligations against what can actually be raised")
ax.set_xlabel("Client")
ax.set_ylabel("USD millions")
ax.legend()
plt.tight_layout()
plt.show()
""")

code("""
# GOLDEN NUMBER 2 — Margarethe Voss-Brenner's EUR 3.4m inheritance tax against her liquid assets.
need = cash_needs[cash_needs["client_id"] == "CL-0003"]
display(need)

mv_tiers = mv.groupby("liquidity_tier")["market_value_base"].sum()
mv_cash = mv.loc[mv["asset_class"] == "Cash and Equivalents", "market_value_base"].sum()
amount = float(need["amount"].iloc[0])

print(f"need                    : EUR {amount:,.0f}  due {need['due_from'].iloc[0]} to {need['due_to'].iloc[0]}"
      f"  ({need['certainty'].iloc[0]})")
print(f"cash on hand            : EUR {mv_cash:,.0f}   -> cover {mv_cash / amount:.2f}x")
print(f"sellable in days (Daily): EUR {mv_tiers.get('Daily', 0):,.0f}   -> cover {mv_tiers.get('Daily', 0) / amount:.2f}x")
print(f"locked                  : EUR {mv_tiers.drop('Daily', errors='ignore').sum():,.0f}")
print()
print("She can pay, but only by selling. The obvious thing to sell is the equity overweight,")
print("which is also the mandate breach in section 5.")
""")

code("""
# The gated private credit fund, and who is sitting behind it.
gated = latest[latest["liquidity_tier"] == "Quarterly Gate"].assign(client_name=lambda d: d["client_id"].map(NAME))
display(gated[["client_id", "client_name", "portfolio_id", "instrument_name", "market_value_usd"]].round(0))

print("Redemption requests that were gated:")
display(
    transactions.loc[transactions["transaction_type"] == "Redemption Request",
                     ["transaction_id", "trade_date", "client_id", "instrument_name", "narrative"]]
)
""")

# ---------------------------------------------------------------- 8. credit
md("""
## 8. Credit and loan-to-value

**What we check.** The five credit facilities and their loan-to-value ratio at each of the five
snapshots, against each facility's own margin-call trigger. LTV here is `drawn ÷ lending_value`,
where lending value is market value after per-asset advance-rate haircuts — not raw market value.

**Why it matters.** Lombard lending is cash advanced against a pledged portfolio. The bank does not
lend against market value — it applies an **advance rate**, or haircut, to each position according
to how liquid and volatile it is, and the resulting **lending value** is the real collateral base.
A diversified bond fund might be advanced at 90%, a single stock at 50%, an illiquid private fund
at 0%. When drawn ÷ lending value crosses the margin-call trigger, the bank can demand more
collateral or sell the client's assets, usually within days. That makes distance-to-trigger the
only alert in this dataset with a hard clock on it. It is also doubly dangerous, because the same
market fall that cuts lending value is when the client least wants to be a forced seller.

**What we found.** Five facilities, USD-equivalent limits from SGD 6m to HKD 70m. **Two breached
their trigger during the period and both were cured by markets rather than by any action.**

| Facility | Client | Trigger | Dec-25 | Feb-26 | Mar-26 | Jun-26 | Aug-26 |
|---|---|---|---|---|---|---|---|
| CF-0005 | Hartono Wijaya Kusuma | 70% | **78.50%** | **75.68%** | 58.86% | 62.18% | 59.15% |
| CF-0001 | Ravi Chandrasekaran | 75% | 63.32% | 59.72% | 61.68% | **75.64%** | 73.71% |
| CF-0002 | Lau Chi Ming | 70% | 53.93% | 53.53% | 65.62% | 67.96% | **69.41%** |

- **CF-0005 was 8.5 points past its trigger at the 2025 year-end baseline.** It was cured on
  2026-03-31 by the Strait of Hormuz closure, which drove the collateral — a coal-mining
  shareholding — up 35.9%. The client did nothing. If the Strait reopens, this facility goes back
  into breach.
- **CF-0001 breached on 2026-06-30**, driven by the June technology drawdown compounded by the
  client drawing a further USD 1.7m on 2026-06-08 to fund a pre-IPO secondary (TXN-0012). Note
  N-004 records the RM warning him and the client proceeding anyway. It cured to 73.71% as tech
  recovered.
- **CF-0002 has never breached but is the one to watch: 69.41% against a 70.0% trigger — 0.59
  points of headroom, and rising every single snapshot.** Its collateral is Lau Chi Ming's Hong Kong
  property complex, which is still falling. This is the same client who owes HKD 60m by mid-2027.

The reason the trend matters more than the level: CF-0002's LTV has risen at every observation
(53.9 → 53.5 → 65.6 → 68.0 → 69.4) while CF-0003 and CF-0004 have been flat and comfortable
throughout. The signal should be direction plus distance, not distance alone — a facility drifting
toward its trigger over four consecutive readings is a conversation you can still have calmly,
whereas one that arrives at the trigger is a conversation about selling this week.

> **Pipeline action.** Stage S3 reshapes `credit_facilities` from its wide `<metric>_<date>` layout
> into long form keyed by `(facility_id, snapshot_date)` — this is the only table in the dataset
> that needs a wide-to-long transform, and doing it once at S3 keeps the date strings out of every
> downstream query. Stage S4 computes `ltv_headroom_pp` (trigger − current LTV) and
> `ltv_trend_direction` over the five snapshots. Lending value must be recomputed independently
> from `holdings.market_value_base × advance_rate_pct` so the published figure can be traced to
> positions rather than trusted from a summary column.
""")

code("""
ltv = facilities.set_index("facility_id")[[f"ltv_pct_{d}" for d in SNAPSHOTS]]
ltv.columns = SNAPSHOTS

credit = facilities[["facility_id", "client_id", "collateral_portfolio_id", "facility_type",
                     "facility_ccy", "credit_limit", "margin_call_ltv_pct", "utilisation_pct_current"]].copy()
credit["client_name"] = credit["client_id"].map(NAME)
credit = credit.set_index("facility_id").join(ltv)
credit["headroom_pp_now"] = credit["margin_call_ltv_pct"] - credit[LAST]
credit["ltv_trend_pp"] = credit[LAST] - credit[FIRST]
credit["ever_breached"] = (ltv.gt(credit["margin_call_ltv_pct"], axis=0)).any(axis=1)

credit[["client_name", "facility_type", "facility_ccy", "credit_limit", "margin_call_ltv_pct",
        *SNAPSHOTS, "headroom_pp_now", "ltv_trend_pp", "ever_breached"]].round(2)
""")

code("""
fig, ax = plt.subplots(figsize=(10, 5.5))
colors = ["#c0392b", "#e08214", "#1f7a3f", "#7f7f7f", "#1f4e79"]
for (facility_id, row), color in zip(ltv.iterrows(), colors):
    trigger = credit.loc[facility_id, "margin_call_ltv_pct"]
    label = f"{facility_id} · {credit.loc[facility_id, 'client_name']} (trigger {trigger:.0f}%)"
    ax.plot(SNAPSHOTS, row.to_numpy(), marker="o", color=color, label=label)
    ax.axhline(trigger, color=color, linestyle=":", linewidth=1, alpha=0.6)

ax.set_title("Loan-to-value across the five snapshots, with each facility's margin-call trigger")
ax.set_xlabel("Snapshot date")
ax.set_ylabel("Loan-to-value (%)")
ax.set_ylim(0, 88)  # leave clear space below the flat facilities for the legend
ax.legend(fontsize=8, loc="lower left")
plt.tight_layout()
plt.show()
""")

code("""
# Every snapshot where a facility sat above its own trigger.
breach_events = []
for facility_id, row in ltv.iterrows():
    trigger = credit.loc[facility_id, "margin_call_ltv_pct"]
    for date, value in row.items():
        if value > trigger:
            breach_events.append({
                "facility_id": facility_id,
                "client_name": credit.loc[facility_id, "client_name"],
                "snapshot_date": date,
                "ltv_pct": value,
                "trigger_pct": trigger,
                "over_by_pp": round(value - trigger, 2),
            })

display(pd.DataFrame(breach_events))
print("Facility drawdowns during the period, from transactions.csv:")
display(
    transactions.loc[transactions["transaction_type"] == "Facility Drawdown",
                     ["transaction_id", "trade_date", "client_id", "currency", "amount", "narrative"]]
)
""")

# ---------------------------------------------------------------- 9. currency & events
md("""
## 9. Currency and event exposure

**What we check.** Two things that travel together. First, how much of each client's wealth sits in
a currency other than the one they are reported in and will spend in. Second, which clients are
exposed to the transmission channels named in `event_log.csv` — with the Strait of Hormuz situation,
which the event log records as **unresolved as of today**, as the worked example.

**Why it matters.** Two exposures clients rarely ask about. **Currency**: a portfolio's job is to
fund a life that will be lived in a particular currency, so a Japanese client retiring to Japan
with 56% of his wealth outside the yen carries a real mismatch even if every holding performs
well. `tax_domicile` rather than `country_of_residence` drives what a disposal actually costs, and
in this book the two differ for most clients. **Events**: the point of a controlled event log is
that the bank can say "this holding moved because of this event" in a form a compliance reviewer
can audit, instead of a model free-associating about geopolitics in front of a client. The sharpest
case is when a client's portfolio and their business are the same bet — a concentration no account
statement can ever show, because half of it sits outside the bank.

**What we found.**

**Currency.** Hartono Wijaya Kusuma is reported in SGD and holds **97.1%** of his wealth in other
currencies, almost all of it one Indonesian rupiah stock; USDIDR moved 16,250 → 17,050 over the
period. Priya Nair Menon 72.1%, Aishah binti Rahman 61.3%, Yamamoto Kenji 56.4%. Yamamoto is the
sharpest case because it is not abstract: note N-021 says he **retires to Japan in 2030 and will
need yen income**, and 56% of his portfolio is not in yen.

**Strait of Hormuz exposure.** Mapping the event log's energy / shipping / Gulf transmission
channels onto holdings gives six exposed clients, and the top two are the ones where **portfolio
risk and source-of-wealth risk are the same risk**:

| Client | Energy + shipping exposure | Source of wealth |
|---|---|---|
| Hartono Wijaya Kusuma (CL-0001) | **45.0%** | Family coal mining and energy group |
| Abdullah Al-Mansoori (CL-0019) | **42.1%** | Gulf logistics, port services, marine chartering |
| Kim Do-Yoon (CL-0015) | 20.4% | Media production |
| Aishah binti Rahman (CL-0005) | 11.1% | Palm oil and property |
| Alistair Pemberton-Hale (CL-0007) | 6.5% | Retired commodities trader |
| Cheung Kwok Wing (CL-0012) | 5.8% | Retired shipping executive |

**Abdullah Al-Mansoori is the scenario client.** 42.1% of his portfolio is in the Strait trade —
a worst-of shipping and energy note (12.9%), Pacific Orient Shipping (11.4%), Global Energy Majors
(8.9%) and Asia Pacific Shipping and Logistics (8.9%). His operating business is Gulf port services
and marine chartering. He is up 25.9% this year and every point of it came from the same conflict.
Note N-025 records him saying "the point of the Asia portfolio was to be uncorrelated with the Gulf
business. It currently is not." Note N-026, dated two weeks ago, records him asking what happens if
the Strait reopens — and the RM's own answer in the file is **"We have not modelled this."** That is
the product gap, written down by the RM herself.

Hartono is the mirror image and the more dangerous position: 45% energy exposure, a coal-mining
family fortune, **and** a Lombard facility whose collateral is that same coal stock and which was in
breach before the energy rally cured it. A Strait reopening hits his portfolio, his family business
and his credit line simultaneously. He also told the RM this account was meant to be the wealth
*not* tied to the mine (N-001), which makes it a suitability conversation as well as a risk one.

> **Pipeline action.** Stage S3 builds a third reference map, `transmission_map`, joining
> `event_log.primary_transmission` channel keywords to instrument ids via `sector`, `region` and
> the look-through map — curated by hand and version-controlled, because keyword matching on free
> text is not defensible on its own. Stage S4 computes `channel_exposure_pct` per client per
> channel and a `wealth_correlation` flag when the channel also matches
> `clients.source_of_wealth`. Every event-driven claim published must cite its `event_log:` id;
> **if no event row supports a statement, the pipeline must not emit it.**
""")

code("""
currency_mix = latest.groupby(["client_id", "instrument_ccy"], as_index=False)["market_value_usd"].sum()
currency_mix["pct"] = currency_mix["market_value_usd"] / currency_mix["client_id"].map(household_totals) * 100
currency_mix["base_ccy"] = currency_mix["client_id"].map(BASE_CCY)

in_base = (
    currency_mix[currency_mix["instrument_ccy"] == currency_mix["base_ccy"]]
    .groupby("client_id")["pct"].sum()
)
fx_risk = pd.DataFrame({
    "client_name": pd.Series(NAME),
    "base_ccy": pd.Series(BASE_CCY),
    "pct_in_base_ccy": in_base,
}).fillna(0.0)
fx_risk["pct_not_in_base_ccy"] = (100 - fx_risk["pct_in_base_ccy"]).round(1)
fx_risk = fx_risk.sort_values("pct_not_in_base_ccy", ascending=False)

print("FX moves over the period (market convention):")
display(FX.loc[[FIRST, LAST]].round(3))
fx_risk.round(1)
""")

code("""
top_fx = fx_risk.head(10).iloc[::-1]
labels = [f"{n} ({c})" for n, c in zip(top_fx["client_name"], top_fx["base_ccy"])]

fig, ax = plt.subplots(figsize=(10.5, 5))
ax.barh(labels, top_fx["pct_not_in_base_ccy"], color="#1f4e79")
ax.set_title("Share of wealth held outside the client's reporting currency")
ax.set_xlabel("Percentage of household wealth not in base currency (%)")
ax.set_ylabel("")
plt.tight_layout()
plt.show()
""")

code("""
# Map the event log's energy / shipping / Gulf channels onto actual instruments.
STRAIT_INSTRUMENTS = [
    "SYN-EQ-0008",  # Global Energy Majors Equity Fund
    "SYN-ST-0101",  # Bara Nusantara Energy (coal)
    "SYN-EQ-0025",  # Asia Pacific Shipping and Logistics
    "SYN-ST-0104",  # Pacific Orient Shipping
    "SYN-CM-0403",  # Broad Commodity Index
    "SYN-SP-0501",  # worst-of energy / tech note
    "SYN-SP-0505",  # worst-of shipping / energy note
    "SYN-EQ-0007",  # Defence and Aerospace
]

print("Events whose transmission channel names energy, shipping or the Gulf:")
display(
    events.loc[
        events["primary_transmission"].str.contains("Energy|shipping|Gulf|LNG|transport", case=False),
        ["event_date", "event_type", "description", "primary_transmission", "severity"],
    ]
)

strait = latest[latest["instrument_id"].isin(STRAIT_INSTRUMENTS)].groupby("client_id")["market_value_usd"].sum()
exposure = pd.DataFrame({
    "client_name": pd.Series(NAME),
    "source_of_wealth": clients.set_index("client_id")["source_of_wealth"],
    "strait_exposure_usd": strait,
    "household_usd": household_totals,
}).dropna(subset=["strait_exposure_usd"])
exposure["strait_pct"] = (exposure["strait_exposure_usd"] / exposure["household_usd"] * 100).round(1)
exposure["strait_exposure_usd_m"] = (exposure["strait_exposure_usd"] / 1e6).round(2)
exposure["household_usd_m"] = (exposure["household_usd"] / 1e6).round(2)
exposure.sort_values("strait_pct", ascending=False)[
    ["client_name", "source_of_wealth", "strait_exposure_usd_m", "household_usd_m", "strait_pct"]
]
""")

code("""
# How the Strait trade actually performed, snapshot by snapshot.
strait_prices = instruments.set_index("instrument_id").loc[
    STRAIT_INSTRUMENTS, [f"price_{d}" for d in SNAPSHOTS]
]
strait_prices.columns = SNAPSHOTS
strait_indexed = strait_prices.div(strait_prices[FIRST], axis=0) * 100
strait_indexed.index = instruments.set_index("instrument_id").loc[STRAIT_INSTRUMENTS, "instrument_name"]

fig, ax = plt.subplots(figsize=(10, 5.5))
for label, row in strait_indexed.iterrows():
    ax.plot(SNAPSHOTS, row.to_numpy(), marker="o", label=label)
ax.axhline(100, color="black", linewidth=0.8)
ax.axvline("2026-03-31", color="#c0392b", linestyle="--", linewidth=1)
ax.annotate(
    "Strait closed 4 March",
    xy=("2026-03-31", 1.0),
    xycoords=("data", "axes fraction"),
    xytext=(0, -12),
    textcoords="offset points",
    fontsize=8,
    color="#c0392b",
    ha="center",
)
ax.set_title("The Strait of Hormuz trade (2025-12-31 = 100)")
ax.set_xlabel("Snapshot date")
ax.set_ylabel("Price indexed to 100 at 2025-12-31")
ax.legend(fontsize=7, loc="upper left")
plt.tight_layout()
plt.show()

display(strait_indexed.round(1))
""")

# ---------------------------------------------------------------- 10. notes vs data
md("""
## 10. RM notes versus the data — "You said / Data says"

**What we check.** We read all 28 relationship-manager notes and, for the ones that contain a
client statement about their own portfolio, put that statement next to the number it is in tension
with.

**Why it matters.** This is where advice actually lives. A private bank's edge is not data, it is
knowing the client, and the most valuable thing in the file is usually the gap between what a
client believes about their money and what their money is doing. The notes also carry facts that
exist in no structured field anywhere: a signed suitability waiver, a dealing restriction on a
board member, a redemption gate that has not yet appeared in a valuation. A recommendation engine
that cannot read them will confidently propose things that are unsuitable, unexecutable, or already
agreed and on file. Presenting the gap as the client's own words beside the computed number is also
what makes it usable in a meeting rather than accusatory.

**What we found.** Nine notes contain a checkable client statement. All nine are contradicted or
sharpened by the data. Six of the strongest:

| Client | You said (RM note) | Data says (computed) |
|---|---|---|
| Margarethe Voss-Brenner | "never taken a risk with money"; wants "something safe and boring" (N-005, N-006) | 71.5% equity in a Conservative mandate capped at 30%; risk tolerance 2/10 |
| Hartono Wijaya Kusuma | The JB relationship is "the part of the family's wealth that is not tied to the mine" (N-001) | 41.4% of his household is one Indonesian coal stock; 45.0% is energy and shipping |
| Aishah binti Rahman | "believes the portfolio is fully aligned" with the family sustainability policy (N-008) | 21.3% of her sustainable mandate is in `sustainability_excluded = Y` instruments |
| Abdullah Al-Mansoori | "the point of the Asia portfolio was to be uncorrelated with the Gulf business" (N-025) | 42.1% is energy and shipping, the same trade as his port-services business |
| Cheung Kwok Wing | "he was told bonds were the safe part"; won't sell at a loss (N-016) | Fixed income cost him USD 2.48m; he is 71 and the longest bond matures in 2045 |
| Zhang Meiling | "dismissive of the suggestion that her exposure to a single name is high once the note is counted" (N-017) | Helios is 22.5% of her household once the note is counted, against a 15% limit |

Two notes contain information that appears **nowhere else in the structured data** and that the
pipeline would otherwise miss entirely:

- **N-010** records a **signed suitability waiver** for Alistair Pemberton-Hale's commodities
  overweight. Without it, his 18.93% versus 10% breach looks like negligence rather than a
  documented client instruction. Any breach alert that cannot see this note will be wrong.
- **N-021** records that Yamamoto Kenji is a **board member with dealing restrictions, and the next
  open window is November 2026**. Any recommendation to trade his employer shares before then is
  unexecutable.

There is also one note that is a to-do rather than an observation: **N-028, dated 19 August, one
week ago — Chalermchai Suphanburi asked whether he should move everything to deposits and Priscilla
has not yet replied.** He is the retiring client who needs USD 1.45m a year from Q2 2027 and whose
bonds are down 6.6%. Selling long bonds at a loss to sit in deposits would crystallise the loss and
give up the yield that is supposed to fund his retirement — a classic capitulation at the wrong
moment, and one an RM has a duty to talk through rather than execute. That is the single most
urgent unactioned item in the book.

> **Pipeline action.** Notes are a **first-class input, not decoration.** Stage S3 normalises
> `rm_notes.json` into one row per note with parsed dates. Stage S4 attaches to each client a
> `stated_beliefs` list (note id, quoted span, topic) and stage S5 pairs each belief with the
> computed fact that confirms or contradicts it, emitting a `belief_gap` signal carrying both the
> `rm_notes:<note_id>` evidence id and the contradicting fact id. Two derived flags must be
> extracted and honoured everywhere downstream: **`waiver_on_file`** (suppresses or reclassifies a
> breach alert) and **`dealing_restriction`** with its open window (suppresses any trade
> recommendation on that instrument until the window opens). Extraction is assisted but
> **RM-reviewed** — the notebook's table was built by reading all 28 notes by hand, and nothing in
> this dataset justifies trusting an unreviewed parse of free text.
""")

code("""
notes.sort_values(["client_id", "note_date"]).assign(
    client_name=lambda d: d["client_id"].map(NAME)
)[["note_id", "client_id", "client_name", "note_date", "channel", "note"]]
""")

code("""
# Build the "You said / Data says" table from computed facts, not from restated text.
def pct_asset(client_id, asset_class):
    frame = latest[latest["client_id"] == client_id]
    return frame.loc[frame["asset_class"] == asset_class, "market_value_usd"].sum() / frame["market_value_usd"].sum() * 100


def pct_instruments(client_id, instrument_ids):
    frame = latest[latest["client_id"] == client_id]
    return frame.loc[frame["instrument_id"].isin(instrument_ids), "market_value_usd"].sum() / frame["market_value_usd"].sum() * 100


fi_change = {}
for client_id in ["CL-0012", "CL-0004"]:
    start = holdings[(holdings["client_id"] == client_id) & (holdings["snapshot_date"] == FIRST)]
    end = holdings[(holdings["client_id"] == client_id) & (holdings["snapshot_date"] == LAST)]
    fi_change[client_id] = (
        end.loc[end["asset_class"] == "Fixed Income", "market_value_base"].sum()
        - start.loc[start["asset_class"] == "Fixed Income", "market_value_base"].sum()
    )

helios_lookthrough = lookthrough.loc[
    (lookthrough["client_id"] == "CL-0013") & (lookthrough["issuer"] == "Helios Cloud Systems"),
    "lookthrough_pct",
].item()

said_vs_data = pd.DataFrame([
    {
        "client": "CL-0003 Voss-Brenner", "note": "N-005 / N-006",
        "you_said": "\\"never taken a risk with money\\"; would prefer \\"something safe and boring\\"",
        "data_says": f"{pct_asset('CL-0003', 'Equity'):.1f}% equity in a Conservative mandate capped at 30%",
    },
    {
        "client": "CL-0001 Wijaya Kusuma", "note": "N-001",
        "you_said": "the JB relationship is the wealth \\"not tied to the mine\\"",
        "data_says": f"{pct_instruments('CL-0001', ['SYN-ST-0101']):.1f}% is one coal stock; "
                     f"{pct_instruments('CL-0001', STRAIT_INSTRUMENTS):.1f}% is energy and shipping",
    },
    {
        "client": "CL-0005 binti Rahman", "note": "N-008",
        "you_said": "believes the portfolio is fully aligned with the family sustainability policy",
        "data_says": f"{susbal_breach['weight_pct'].sum():.1f}% of the mandate is in excluded instruments",
    },
    {
        "client": "CL-0019 Al-Mansoori", "note": "N-025",
        "you_said": "the Asia portfolio was meant to be uncorrelated with the Gulf business",
        "data_says": f"{pct_instruments('CL-0019', STRAIT_INSTRUMENTS):.1f}% is the same energy and shipping trade",
    },
    {
        "client": "CL-0012 Cheung", "note": "N-016",
        "you_said": "was told bonds were the safe part; will not sell at a loss",
        "data_says": f"fixed income cost USD {abs(fi_change['CL-0012']):,.0f}; longest bond matures 2045, client is 71",
    },
    {
        "client": "CL-0013 Zhang", "note": "N-017",
        "you_said": "dismissive that single-name exposure is high once the note is counted",
        "data_says": f"Helios is {helios_lookthrough:.1f}% of the household after look-through, limit 15%",
    },
    {
        "client": "CL-0007 Pemberton-Hale", "note": "N-010",
        "you_said": "instructed more gold above the ceiling; suitability waiver on file",
        "data_says": f"commodities {pct_asset('CL-0007', 'Commodities'):.1f}% vs 10% max — breach is documented, not drift",
    },
    {
        "client": "CL-0016 Yamamoto", "note": "N-021",
        "you_said": "board dealing restrictions; next open window November 2026",
        "data_says": f"{fx_risk.loc['CL-0016', 'pct_not_in_base_ccy']:.1f}% not in JPY, retiring to Japan in 2030",
    },
    {
        "client": "CL-0004 Suphanburi", "note": "N-028 (19 Aug, unanswered)",
        "you_said": "asked whether he should move everything to deposits",
        "data_says": f"fixed income cost USD {abs(fi_change['CL-0004']):,.0f}; needs USD 1.45m a year from Q2 2027",
    },
])
said_vs_data
""")

# ---------------------------------------------------------------- 11. imperfections
md("""
## 11. Data imperfections catalogue

**What we check.** Everything in the data that is wrong, stale, missing, or structurally surprising
— found by the checks in sections 1 to 10 rather than assumed.

**Why it matters.** The brief says the dataset contains deliberate real-world imperfections and that
noticing them counts. More practically: each one below changes a line of pipeline code, and two of
them change a number we would otherwise put on a slide.

**What we found.** Ten items. The two marked **high** materially change results if ignored.

The most consequential is not a broken value at all — it is a structural property. **`holdings.csv`
and `transactions.csv` do not reconcile.** Across all five snapshots exactly one position quantity
ever changes (Alistair Pemberton-Hale's gold ETF, 6,000 → 8,000 units) and six new positions appear
(the structured-product subscriptions). Nothing is ever sold, no cash balance ever moves, and the
148 dividends, 92 coupons, 48 management fees and 4 withdrawals in `transactions.csv` leave no trace
in `holdings.csv`. Two consequences: the pipeline must treat **holdings as the sole source of truth
for positions and transactions as an event and narrative source only**; and **book growth is
overstated by USD 14.7m** because those seven purchases were never funded from anything.

The second high-severity item is the **inherited portfolio PF-0005**. All nine positions carry
`acquired_date = 2026-02-16` — the date of the transfer-in — yet they appear in the 2025-12-31
snapshot, two months *before* they were acquired. TXN-0018 explains it: the portfolio came in from
another institution after the account holder's spouse died, and "tax lot history was not provided
for all positions". So the history is a backfill, and one position (Nordvind Industrial AB) has no
cost basis at all. **Any unrealised gain or tax-loss-harvesting calculation on this client will be
wrong**, which matters because she is the client with the largest mandate breach and a tax bill due
in four months.
""")

code("""
imperfections = pd.DataFrame([
    {
        "id": "DQ-01", "severity": "high",
        "where": "holdings.csv vs transactions.csv",
        "what": "Only 1 of 206 position quantities ever changes and 6 new positions appear; nothing is "
                "ever sold, no cash balance moves, and no dividend, coupon, fee or withdrawal is "
                "reflected. The two files do not reconcile.",
        "pipeline_should": "Treat holdings as the only source of truth for positions and valuations. "
                           "Use transactions for events, narratives and client intent only, never to "
                           "roll forward balances.",
    },
    {
        "id": "DQ-02", "severity": "high",
        "where": "holdings.csv — 6 structured products + 1 gold purchase",
        "what": "USD 14.7m of new positions appear with no offsetting sale or cash reduction, "
                "inflating book growth from roughly +2.2% to the headline +3.30%.",
        "pipeline_should": "Report performance from the price and FX effects only. Show subscriptions "
                           "as a separate 'new positions' line, never inside a return figure.",
    },
    {
        "id": "DQ-03", "severity": "high",
        "where": "holdings.csv — PF-0005 (CL-0003), all 9 rows",
        "what": "acquired_date = 2026-02-16 for every position, but the positions appear in the "
                "2025-12-31 and 2026-02-27 snapshots — acquired after the date they are reported at. "
                "TXN-0018 shows the portfolio was transferred in on that date and the history backfilled.",
        "pipeline_should": "Treat acquired_date on transferred-in portfolios as the transfer date, not "
                           "the purchase date. Suppress holding-period and tax-lot logic for CL-0003 and "
                           "say why.",
    },
    {
        "id": "DQ-04", "severity": "medium",
        "where": "holdings.csv — SYN-ST-0107 Nordvind Industrial AB, 5 rows",
        "what": "avg_cost_local, cost_basis_base, unrealised_pnl_base and unrealised_pnl_pct are all null. "
                "Cost basis was not supplied on transfer-in.",
        "pipeline_should": "Show unrealised P&L as 'not available' for this position. Never impute a cost "
                           "basis; an invented tax number is worse than a blank.",
    },
    {
        "id": "DQ-05", "severity": "medium",
        "where": "holdings.csv — SYN-AL-0308 Aranya Technologies, all 5 snapshots",
        "what": "valuation_date is 2025-09-30 at every snapshot, so the mark is 11 months stale at "
                "today, and it is 68.4% of CL-0002's household wealth. TXN-0019 confirms a June review "
                "left the carrying price unchanged.",
        "pipeline_should": "Surface valuation age wherever this position is shown. Exclude stale private "
                           "marks from performance attribution and flag concentration built on them.",
    },
    {
        "id": "DQ-06", "severity": "low",
        "where": "instruments.csv / holdings.csv — SYN-SP-0506",
        "what": "sector is null for the Asia Banks autocallable (5 holdings rows and 1 instrument row).",
        "pipeline_should": "Fall back to sub_asset_class and region for sector grouping; never drop the "
                           "row from a sector chart.",
    },
    {
        "id": "DQ-07", "severity": "low",
        "where": "clients.csv — CL-0017",
        "what": "age is null. Fong Enterprises Family Office is a legal entity, not a person.",
        "pipeline_should": "Guard every age-based rule (retirement horizon, life stage) against nulls "
                           "rather than defaulting to a number.",
    },
    {
        "id": "DQ-08", "severity": "medium",
        "where": "instruments.csv — private market marks",
        "what": "Private equity and private real estate prices repeat across consecutive snapshots "
                "(Meridian PE VII holds 1420.00 from Dec to Mar; the two direct properties hold one "
                "price for three snapshots). This is normal quarterly reporting lag, not an error.",
        "pipeline_should": "Exclude quarterly-marked assets from short-horizon attribution and label "
                           "them 'valued as at <date>' rather than implying a live price.",
    },
    {
        "id": "DQ-09", "severity": "medium",
        "where": "holdings.csv — advance_rate_pct on Illiquid structured products",
        "what": "Illiquid structured products carry advance rates from 0% to 60%, so 'Illiquid' does not "
                "imply zero collateral value. Lending value must come from advance_rate_pct, not from "
                "the liquidity tier.",
        "pipeline_should": "Compute lending value as market value x advance_rate_pct per position. Never "
                           "infer collateral value from liquidity_tier.",
    },
    {
        "id": "DQ-10", "severity": "medium",
        "where": "market_context.csv FX conventions",
        "what": "Pairs are quoted in market convention: USDSGD is SGD per USD, EURUSD is USD per EUR. "
                "Dividing when you should multiply gives a plausible-looking wrong answer.",
        "pipeline_should": "Use one tested conversion helper everywhere (see to_usd above) and unit-test "
                           "it against holdings.market_value_usd / market_value_local.",
    },
])
imperfections
""")

code("""
# Evidence for the two high-severity structural findings.
quantities = holdings.pivot_table(
    index=["portfolio_id", "instrument_id"], columns="snapshot_date", values="quantity", aggfunc="sum"
).reindex(columns=SNAPSHOTS)

changed = quantities[quantities.nunique(axis=1, dropna=True) > 1]
appeared = quantities[quantities[FIRST].isna() & quantities[LAST].notna()]
vanished = quantities[quantities[FIRST].notna() & quantities[LAST].isna()]

print(f"positions whose quantity ever changes : {len(changed)} of {len(quantities)}")
print(f"positions that appear mid-period      : {len(appeared)}")
print(f"positions that are ever sold down     : {len(vanished)}")
display(changed)
display(appeared)

print("\\nDQ-03 / DQ-04 — the inherited portfolio PF-0005:")
display(
    holdings.loc[
        (holdings["portfolio_id"] == "PF-0005") & (holdings["snapshot_date"] == FIRST),
        ["snapshot_date", "instrument_name", "acquired_date", "avg_cost_local",
         "cost_basis_base", "unrealised_pnl_base"],
    ]
)
print("\\nDQ-05 — the stale private mark:")
display(
    holdings.loc[
        holdings["valuation_date"] != holdings["snapshot_date"],
        ["snapshot_date", "portfolio_id", "instrument_name", "market_value_base", "valuation_date"],
    ]
)
""")

# ---------------------------------------------------------------- 12. handoff
md("""
## 12. Findings summary and frozen signal shortlist

This section is the handoff to the pipeline build. Nothing below is aspirational — every signal is
computable from the columns profiled above, and every threshold was chosen after seeing the actual
distribution in sections 3 to 10.

### The eight signals, ranked

Ranked by how confidently an RM could defend the resulting alert to a client and to compliance.

| # | Signal | Definition | Threshold | Inputs | Why it matters |
|---|---|---|---|---|---|
| 1 | **Mandate band breach** | Household or portfolio allocation per asset class versus `min_pct`/`max_pct`, excluding Custody | any breach; **escalate above 10pp** | `holdings`, `portfolios`, `mandates` | The most defensible alert there is: documented rule, documented number, documented gap. Fires 14 times for 9 of 20 clients. |
| 2 | **Funding gap** | (cash + Daily-liquid assets) versus cash needs due within 12 months plus uncalled commitments | **cash cover < 1.0x** warn; **Daily cover < 1.5x** escalate | `planned_cash_needs`, `commitments`, `holdings.liquidity_tier` | Deadlines are the only thing in this data that cannot be deferred. Nine clients cannot pay from cash. |
| 3 | **Collateral stress** | LTV per facility per snapshot versus `margin_call_ltv_pct`, plus the trend across snapshots | **within 5pp** of trigger, or **rising at 3+ consecutive snapshots** | `credit_facilities` | Hard deadline attached. Two facilities breached; a third is 0.59pp away and rising. |
| 4 | **Look-through concentration** | Single-issuer exposure at household level, adding structured products via `underlying_reference` and same-issuer instruments | above the household's tightest `max_single_position_pct` | `holdings`, `instruments.underlying_reference`, issuer map | The insight no existing report produces. Finds 12.9% exposure to a stock CL-0019 does not own a share of. |
| 5 | **Belief-versus-data gap** | Client statements parsed from `rm_notes` placed beside the contradicting computed fact | manual pairing, RM-reviewed | `rm_notes`, all computed signals | The core product feature. Nine of 28 notes contain a checkable claim; all nine are contradicted. |
| 6 | **Event exposure** | Share of household in instruments matching an `event_log` transmission channel | **> 15%** of household on one channel | `event_log`, `instruments`, `holdings` | The only auditable bridge from world events to a client. Two clients above 40% on the Strait channel. |
| 7 | **Currency mismatch** | Share of wealth outside the client's base currency, weighted by whether obligations are in the base currency | **> 40%** not in base currency | `holdings.instrument_ccy`, `clients.base_currency`, `cash_needs.currency` | Cost the USD-reported book USD 8.3m that nobody actually lost. Four clients above 55%. |
| 8 | **Suitability drift** | Realised volatility and drawdown of the household versus `risk_tolerance_score` | conservative profile (score ≤ 3) with a **loss worse than −5%** in base currency | `holdings` across snapshots, `clients.risk_profile` | Catches the inversion this year: the low-tolerance clients are the ones who lost money. |

### Preprocessing decisions the pipeline must implement

1. **Holdings are the source of truth for positions.** Transactions are events and narrative only.
   Never roll balances forward from transactions (DQ-01).
2. **Report performance in the client's base currency.** Report the book in USD. Never mix them —
   CL-0009 is −4.0% in one and +2.0% in the other (section 4).
3. **Separate price effect, FX effect and new positions.** Only the first two are performance
   (DQ-02).
4. **Aggregate to household before testing any concentration or allocation rule**, then also test
   per portfolio, because mandates bind per portfolio (section 6).
5. **Exclude Custody portfolios from mandate tests, include them in wealth and risk.** PF-0002,
   PF-0004 and PF-0021 are custody; PF-0004 alone is 68.4% of CL-0002's wealth (section 5).
6. **Compute lending value as market value × `advance_rate_pct` per position.** Never infer
   collateral value from `liquidity_tier` (DQ-09).
7. **Use one tested FX helper**, respecting market quoting convention, validated against
   `market_value_usd ÷ market_value_local` (DQ-10).
8. **Carry a valuation-age field on every position** and suppress stale private marks from
   attribution (DQ-05, DQ-08).
9. **Never impute a missing cost basis.** Show "not available" (DQ-04).
10. **Ground every causal claim in an `event_log` row id.** If no row supports it, do not say it.

### The top three client stories for the demo

**1 — Margarethe Voss-Brenner (CL-0003): the inherited portfolio nobody has fixed.**
58, widowed in February, risk tolerance 2 out of 10, told her RM she "has never taken a risk with
money" and wants "something safe and boring". She holds **71.5% equity against a 30% Conservative
cap** — the largest breach in the book — with **9.15% fixed income against a 45% floor**. A
**confirmed EUR 3.4m German inheritance-tax instalment falls due between October and December
2026**, and her cash covers **0.46x** of it. She is also the client with the broken cost basis, so
we must tell her we cannot compute her tax position on one holding. The story lands because the
liquidity problem and the compliance problem have one shared solution: sell the equity overweight to
fund the tax bill. Every number traces to nine source rows.

**2 — Abdullah Al-Mansoori (CL-0019): the hedge that is not a hedge.**
Gulf port services and marine chartering entrepreneur. **42.1% of his portfolio is the same energy
and shipping trade his business runs on** — a worst-of shipping and energy note (12.9%), Pacific
Orient Shipping (11.4%), Global Energy Majors (8.9%), Asia Pacific Shipping (8.9%). He is **up 25.9%
this year**, entirely from a conflict that also enriched his operating company. He told the RM the
Asia portfolio "was meant to be uncorrelated with the Gulf business. It currently is not" (N-025),
and on 12 August he asked what happens if the Strait reopens. The file's own answer is **"We have
not modelled this" (N-026).** This is the scenario-rehearsal demo, and the RM wrote the requirement
herself.

**3 — Lau Chi Ming (CL-0014): four instruments, one bet, and a margin call approaching.**
**29.5% of his household is a single Hong Kong property issuer** once you count the shares (9.5%),
the perpetual bond (12.9%) and the accumulator (7.1%) — none of which looks alarming alone. Add the
Mid-Levels apartment and Hong Kong property is **49%** of his wealth. Every one of those instruments
fell: accumulator −41.7%, perpetual −31.1%, shares −24.2%. His Lombard facility has climbed to
**69.41% LTV against a 70.0% trigger, rising at every snapshot**, and he owes an **HKD 60m
redevelopment contribution by mid-2027** against USD 1.5m of cash. Selling to fund it shrinks the
collateral behind the facility that is already almost breached. The RM told him in March that "the
perpetual, the shares, the accumulator and his own development business are all the same bet"
(N-018) and he answered "that is why he is confident."

### Three things that surprised us

1. **The book's +3.30% is not performance.** USD 14.7m of the USD 19.0m gain is unfunded new
   positions that appear in `holdings` with nothing sold to pay for them. Strip those out and the
   book returned **+0.76% in USD** — prices added 2.19pp and the rising dollar took 1.43pp back off,
   and that 1.43pp is a translation effect no client actually experienced.
2. **Risk profile and outcome are inverted.** In base currency the two worst performers in the book
   are the two Income clients (−7.0%, −6.6%) and neither Conservative client made money, while the
   two Balanced Growth clients and the Dynamic Opportunistic client are all above +23%. The clients
   who were told bonds are the safe part are the ones who lost.
3. **Two margin-call breaches were cured by geopolitics, not by anyone doing anything.** CF-0005 sat
   8.5 points past its trigger at the 2025 baseline and was rescued on 31 March by the Strait
   closure lifting the coal stock pledged against it. Nobody acted. If the Strait reopens, the same
   client loses on his portfolio, his family business and his credit line simultaneously — and the
   RM has no model for that, by her own note (N-026).
""")

code("""
print(f"EDA complete — {TODAY}")
print(f"clients {len(clients)} · portfolios {len(portfolios)} · positions {len(holdings)} "
      f"· instruments {len(instruments)} · snapshots {len(SNAPSHOTS)}")
print()
print(f"book value            : USD {book.loc[LAST] / 1e6:,.1f}m  ({(book.loc[LAST] / book.loc[FIRST] - 1) * 100:+.2f}% headline)")
print(f"  of which price      : USD {effects['price_effect'] / 1e6:+,.1f}m")
print(f"  of which FX         : USD {effects['fx_effect'] / 1e6:+,.1f}m")
print(f"  of which new posns  : USD {effects['new_position_effect'] / 1e6:+,.1f}m  <- not performance")
print()
print(f"mandate band breaches : {len(breaches)} across {breaches['client_id'].nunique()} clients")
print(f"clients short of cash : {(liquidity['cash_cover_x'] < 1).sum()} of {len(liquidity)}")
print(f"facilities ever in breach : {int(credit['ever_breached'].sum())} of {len(credit)}")
print(f"data imperfections logged : {len(imperfections)} ({(imperfections['severity'] == 'high').sum()} high)")
""")

# ---------------------------------------------------------------- build
notebook = nbf.v4.new_notebook()
notebook.cells = [
    nbf.v4.new_markdown_cell(text) if kind == "md" else nbf.v4.new_code_cell(text)
    for kind, text in CELLS
]
notebook.metadata = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.13"},
}

out = Path(__file__).parent / "eda.ipynb"
nbf.write(notebook, out)
print(f"wrote {out} — {len(notebook.cells)} cells")
