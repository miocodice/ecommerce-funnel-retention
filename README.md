# E-commerce Funnel & Retention Analysis

Production-grade Data Engineering & Product Analytics project implementing **Clickstream Sessionization**, **Conversion Funnel Analysis**, **Time-to-Buy (TTB) Tracking**, **Polars Cohort Retention Matrix Engine**, and **Apache Superset BI Data Marts** on multi-million row e-commerce clickstream data.


## 1. Visual Analytics & Core Insights

### 1.1 Conversion Funnel & Drop-off Friction
Tracks strict sequential user transitions ($View \rightarrow Cart \rightarrow Purchase$) per session, isolating drop-off bottlenecks and measuring step conversion rates alongside Time-to-Buy (TTB).

![E-Commerce Conversion Funnel](docs/images/conversion_funnel.png)

#### 📊 Analytical Findings:
- **View $\rightarrow$ Cart Drop-off (40.7% Loss)**: The primary friction point in the customer journey. 407 out of 1,000 unique users browse products but never add them to the cart. This points to discovery friction, unclear pricing/shipping details on product pages, or lack of strong call-to-actions.
- **Cart $\rightarrow$ Purchase Drop-off (38.1% Abandonment)**: Out of 593 users who demonstrated high purchase intent by adding items to cart, 226 drop off before checkout.
- **Overall Conversion Rate**: 36.7% ($View \rightarrow Purchase$), with a cumulative 63.3% loss across the entire funnel.

#### 💡 Actionable Business Hypotheses & Growth Levers:
1. **Reduce View $\rightarrow$ Cart Friction**:
   - **Delivery & Price Transparency**: Add an instant delivery calculator and shipping cost estimator directly on the Product Detail Page (PDP) to eliminate post-cart surprise fees.
   - **Social Proof & Urgency Triggers**: Display real customer ratings, verified buyer badges, and stock scarcity indicators (*"Only 3 items left in stock"*).
2. **Recover Abandoned Carts (Cart $\rightarrow$ Purchase)**:
   - **Frictionless Checkout**: Implement One-Click Checkout (Apple Pay, Google Pay, Fast Checkout) to reduce multi-step form exhaustion.
   - **Automated Omnichannel Retargeting**: Trigger automated push/email recovery sequences at $T+1h$ and $T+24h$ offering limited-time perks (e.g., free delivery or 5% cart discount).

---

### 1.2 Cohort User Retention Matrix
High-performance cohort retention engine computed with **Polars LazyFrames**, grouping users by their initial acquisition week and tracking behavioral decay over subsequent weeks.

![Weekly Cohort Retention Heatmap](docs/images/cohort_retention_heatmap.png)

#### 📊 Analytical Findings:
- **Steep Week 1 Cliff (65–75% Churn)**: Retention plummets to 25.8%–35.9% by Week 1 across all cohorts. The first 7 days represent the highest attrition risk.
- **Long-tail Retention Decay (Week 3+)**: By Week 3 and beyond, active user retention drops below 5%, flattening out at ~1–3%. The absence of a stable retention plateau indicates a *Leaky Bucket* dynamic where revenue relies disproportionately on top-of-funnel user acquisition rather than repeat engagement.

#### 💡 Actionable Business Hypotheses & Growth Levers:
1. **Strengthen Week 1 Activation**:
   - **Post-Purchase Onboarding & Engagement**: Send personalized post-purchase sequences containing order tracking, unboxing guides, and complementary accessory recommendations.
   - **Time-Sensitive Welcome Rewards**: Grant first-time buyers reward points that expire within 10–14 days (*"You have $10 in store credit expiring this Sunday"*).
2. **Build a Sustainable Retention Plateau**:
   - **Tiered Loyalty Program**: Introduce points accumulation, VIP tiers, and exclusive early access to sales for frequent buyers.
   - **Automated Win-Back Triggers**: Deploy automated reactivation campaigns for users who have been inactive for >21 days with personalized product recommendations based on past browsing history.

---

### 1.3 Executive Daily KPI Trends
Continuous tracking of Daily Active Users (DAU), Gross Merchandise Volume (Revenue), and Average Order Value (AOV) across all product categories.

![Daily Executive KPI Trends](docs/images/daily_kpi_trends.png)

#### 📊 Analytical Findings:
- **Revenue Volatility & Category Skew**: Daily revenue exhibits sharp spikes followed by low plateaus, driven by sporadic purchases in high-ticket categories (`electronics`, `appliances`) rather than steady consumer volume.
- **AOV Fluctuations**: Average Order Value fluctuates heavily depending on premium brand mix (e.g., Apple/Samsung vs apparel/accessories).

#### 💡 Actionable Business Hypotheses & Growth Levers:
1. **Revenue Smoothing & AOV Expansion**:
   - **Dynamic Bundle Recommendations**: Implement AI-driven *"Frequently Bought Together"* bundles (e.g., Smartphone + Screen Protector + Fast Charger at 12% bundle discount) to boost baseline basket size.
   - **Mid-Week Flash Events**: Launch mid-week promotions (e.g., *"Tech Wednesday"*, mid-week free delivery) to flatten weekend-dependent revenue volatility.
2. **Financing & High-Ticket Conversion**:
   - **BNPL Integration**: Add *"Buy Now, Pay Later"* (installment payments) on items over $200 to lower the psychological hurdle for high-value appliances and electronics.

---

## 2. Context & Data Architecture

This project models and analyzes user shopping journeys, friction points, and retention dynamics in multi-category retail environments.

### Data Schema (`raw_events`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `event_time` | `TIMESTAMPTZ` | UTC timestamp of the clickstream event |
| `event_type` | `VARCHAR(30)` | Action type (`view`, `cart`, `remove_from_cart`, `purchase`) |
| `product_id` | `BIGINT` | Unique product SKU identifier |
| `category_id` | `BIGINT` | Broad category identifier |
| `category_code` | `VARCHAR(255)` | Hierarchical category string (e.g. `electronics.smartphone`) |
| `brand` | `VARCHAR(255)` | Manufacturer brand name |
| `price` | `NUMERIC(10, 2)` | Product price in USD |
| `user_id` | `BIGINT` | Unique user identifier |
| `user_session` | `UUID` | Frontend clickstream session identifier |

---

## 3. Technical Stack & Key Decisions

- **Database**: PostgreSQL 15+ with Range Partitioning by `event_time` and composite indexes on `(user_id, event_time)` and `(event_type, event_time)`.
- **SQL Analytics**: Strict use of Window Functions (`LAG`, `ROW_NUMBER`, `FIRST_VALUE`, `SUM() OVER`) and CTEs. Zero reliance on plain `GROUP BY` for funnel ordering.
- **Python Engine**: **Polars** (`polars>=0.20.0`) utilizing lazy evaluation (`scan_parquet` / `scan_csv`) to process tens of millions of clickstream events in streaming mode with minimal RAM footprint.
- **Visualization**: Interactive Plotly Cohort Heatmaps (`plotly.graph_objects`), Matplotlib/Seaborn report exports, and Apache Superset BI Data Marts.

---

## 4. Quick Start & Execution Guide

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
