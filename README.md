# Qafila gross margin

Submitted by: Nouf Alharthi — academy: @SDAIAAcademy

The task, rules and grading are in [BRIEF.md](BRIEF.md).

```bash
uv sync
uv run python tools/make_data.py          # data/
uv run python run.py                      # data/ -> warehouse/ (DuckDB + Iceberg)
uv run python tools/check.py              # contract self-check
```

## Design

SQLite database + supplier CSV files → DuckDB (raw) → dbt (staging) → Silver / Quality → Gold → Apache Iceberg

| Model | Layer | Grain (one row per ...) | Materialization |
|---|---|---|---|
| `stg_supplier_prices` | staging | Supplier price record | View |
| `product_cost_history` | silver | SKU and cost version | Table |
| `weekly_margin` | gold | Week, city, and category | Table |
| `price_quarantine` | quality | Rejected supplier price record | Table |

**How the SCD2 history is built:** 

I keep the previous cost if a product is missing from a weekly file. I only add a new version when the cost changes. If there's a correction file, I use the corrected price instead of the original one.

**How each order line finds its cost:** 

I match each order line with the cost valid on its order date. If there's no matching cost, I still include the line in revenue and count it as uncosted.

## Data problems I found

| Problem | Where | Rows affected | What I did |
|---|---|---|---|
| Invalid costs | Supplier CSV files | 4 | Moved them to quarantine |
| Unknown SKUs | Supplier CSV files | 3 | Moved them to quarantine |
| Different number formats | Supplier CSV files | 126 | Normalized the costs |
| Different column names | Supplier CSV files | 169 | Handled both cost column names |

## Tests

| Test | On | What it protects against |
|---|---|---|
| `positive_costs` | Silver | Invalid costs |
| `one_current_cost` | Silver | Multiple current costs |
| `no_overlapping_costs` | Silver | Overlapping cost dates |
| `no_repeated_cost` | Silver | Unnecessary cost versions |
| `margin_consistency` | Gold | Incorrect margin calculations |
| `accepted_values` | Quality | Invalid quarantine reasons |
| `not_null` | Multiple models | Missing values |

## Re-runs and the correction

I ran the pipeline twice with the same data, and all three Iceberg tables stayed unchanged.

Then I added the Week 39 correction and ran it again. The cost history increased from 633 to 637 rows, and the weekly margin was updated. All 22 checks passed.

I compared the margin before and after the correction using Iceberg snapshots:

- **Before snapshot:** `6845631290659025227`
- **After snapshot:** `5604004991215127956`
- **Week:** 39
- **City:** Dammam
- **Category:** Bakery
- **Margin before:** 726.72 SAR
- **Margin after:** 729.45 SAR

The old snapshot still shows 726.72 SAR, so the previous result was preserved.

## What I'd do next

I would use incremental processing instead of rebuilding the tables every time. I would also add monitoring and improve the pipeline to handle daily supplier files.

## AI assistance

I used ChatGPT as a supporting tool for troubleshooting and clarifying technical concepts during development.

### Additional Note

I accidentally removed some comments and docstrings while cleaning up the code. This caused an issue in three scripts (`check.py`, `make_data.py`, and `qafila_data.py`) because they were using `__doc__` for their CLI descriptions.

I fixed the issue by replacing the `__doc__` references with fixed description strings without changing the original functionality.

After the fix, I tested all three scripts successfully, and `tools/check.py` passed all **22/22 checks**.