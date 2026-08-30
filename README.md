# E-commerce Funnel & Retention Analysis

Production-grade pet project implementing **Clickstream Sessionization**, **Conversion Funnel Analysis**, **Time-to-Buy (TTB) Tracking**, **Polars Cohort Retention Matrix Engine**, and **Apache Superset Data Marts** based on multi-million row Kaggle eCommerce behavior data.

---

## 1. Context & Data Architecture

This project analyzes user shopping journeys, friction points, and retention dynamics in multi-category e-commerce stores.

### Data Schema (`raw_events`)
- `event_time` (`TIMESTAMPTZ`): UTC timestamp of event.
- `event_type` (`VARCHAR`): Action type (`view`, `cart`, `remove_from_cart`, `purchase`).
- `product_id` (`BIGINT`): Unique product SKU ID.
- `category_id` (`BIGINT`): Broad category ID.
- `category_code` (`VARCHAR`): Hierarchical category string (e.g., `electronics.smartphone`).
- `brand` (`VARCHAR`): Manufacturer brand name.
- `price` (`NUMERIC(10, 2)`): Product price in USD.
- `user_id` (`BIGINT`): Unique user ID.
- `user_session` (`UUID`): Frontend clickstream session identifier.

---

## 2. Technical Stack & Key Decisions

- **Database**: PostgreSQL 15+ with Range Partitioning by `event_time` and composite indexes on `(user_id, event_time)` and `(event_type, event_time)`.
- **SQL Analytics**: Strict use of Window Functions (`LAG`, `ROW_NUMBER`, `FIRST_VALUE`, `SUM() OVER`) and CTEs. Zero reliance on plain `GROUP BY` for funnel ordering.
- **Python Engine**: **Polars** (`polars>=0.20.0`) utilizing lazy evaluation (`scan_parquet` / `scan_csv`) to process tens of millions of clickstream events with low RAM footprint.
- **Visualization**: Interactive Plotly Cohort Heatmaps (`plotly.graph_objects`) and Apache Superset BI Data Marts.

---

## 3. Quick Start & Execution Guide

### Step 1: DDL & Database Sessionization (SQL)
Run `sql/01_ddl_and_sessionization.sql` in PostgreSQL:
```bash
psql -h localhost -U postgres -d ecommerce_db -f sql/01_ddl_and_sessionization.sql
```
> [!NOTE]
> Reconstructs missing/broken frontend sessions using a **30-minute inactivity window** via `LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time)`.

### Step 2: Funnel & Time-to-Buy (TTB) Calculation (SQL)
Run `sql/02_funnel_and_dropoff.sql`:
```bash
psql -h localhost -U postgres -d ecommerce_db -f sql/02_funnel_and_dropoff.sql
```
> [!NOTE]
> Computes strict sequential step progression (`View` $\rightarrow$ `Cart` $\rightarrow$ `Purchase`) per user session, calculating unique users, step conversion rates (CR %), drop-off rates (% loss), and TTB (Time-to-Buy in minutes).

### Step 3: Cohort & Retention Analysis (Python Polars)
Install dependencies and run the cohort analysis engine:
```bash
pip install -r requirements.txt

# 1. (Optional) Generate synthetic dataset
python python/generate_sample_data.py

# 2. Run weekly cohort retention study & generate interactive heatmap
python python/retention_analysis.py --input data/sample_raw_events.parquet --granularity W --output_html docs/cohort_retention_heatmap.html
```
> [!TIP]
> Open `docs/cohort_retention_heatmap.html` in any browser to inspect the interactive Plotly heatmap with retention percentages and hover details.

### Step 4: BI Analytical Views & Superset Dashboard
Deploy `sql/03_superset_views.sql` to expose production data marts to Apache Superset:
- `v_kpi_daily`: Daily DAU, Revenue, AOV, ARPU, Overall CR.
- `v_funnel_summary`: Daily funnel aggregated by category & brand.
- `v_cohort_retention`: Flat cohort dataset for BI heatmaps.

Refer to [`docs/superset_dashboard_spec.md`](docs/superset_dashboard_spec.md) for full dashboard specifications, chart configurations, and Jinja filters.
