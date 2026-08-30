# Apache Superset Dashboard Specification: E-commerce Funnel & Retention

Detailed architectural specification and configuration guide for constructing the production **E-commerce Funnel & Retention Analysis** dashboard in Apache Superset.

---

## 1. Dashboard Layout & Visual Grid

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ Global Filters: [ Date Range: Last 30 Days ] [ Category: All ] [ Brand: All ]    │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Row 1: KPI Summary Cards                                                         │
│ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌────────────────────────┐ │
│ │ Total Revenue │ │    DAU Avg    │ │  AOV (Mean)   │ │ Overall Conversion Rate│ │
│ │   $1,425,800  │ │    45,210     │ │    $128.50    │ │         3.42%          │ │
│ └───────────────┘ └───────────────┘ └───────────────┘ └────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Row 2: Funnel & Drop-off Friction Analysis                                       │
│ ┌──────────────────────────────────────┐ ┌─────────────────────────────────────┐ │
│ │ Chart 1: Conversion Funnel (Bar/Area)│ │ Chart 2: Drop-off Rate by Category  │ │
│ │ View (100%) -> Cart (35%) -> Buy(8%) │ │ (View->Cart vs Cart->Purchase)      │ │
│ └──────────────────────────────────────┘ └─────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Row 3: Cohort Retention Analysis                                                 │
│ ┌──────────────────────────────────────────────────────────────────────────────┐ │
│ │ Chart 3: Weekly Cohort Retention Heatmap (Pivot Table v2)                    │ │
│ │ Rows: Cohort Week | Columns: Week 0 .. Week 8 | Cell: Retention Rate %       │ │
│ └──────────────────────────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Row 4: Category & Brand Performance Deep Dive                                    │
│ ┌──────────────────────────────────────┐ ┌─────────────────────────────────────┐ │
│ │ Chart 4: Top Revenue Categories      │ │ Chart 5: Brand CR vs Revenue Matrix │ │
│ │ (Treemap: Size=Revenue, Color=CR)    │ │ (Scatter: X=Revenue, Y=CR, Size=DAU)│ │
│ └──────────────────────────────────────┘ └─────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Dataset Connections & Virtual Data Sources

Connect Superset to PostgreSQL using SQLAlchemy URI:
`postgresql+psycopg2://<user>:<password>@<host>:5432/<dbname>`

### Primary Virtual Data Marts:
1. `v_kpi_daily`: High-level daily metrics (DAU, Revenue, Orders, AOV, Conversion Rate).
2. `v_funnel_summary`: Aggregated conversion funnel breakdown by day, category, and brand.
3. `v_cohort_retention`: Flat cohort matrix formatted for Superset Pivot Table v2 / Heatmap.

---

## 3. Detailed Chart Specifications

### Chart 1: Executive KPI Cards (Row 1)
- **Dataset**: `v_kpi_daily`
- **Visualization Type**: Big Number with Trendline / Card
- **Metrics**:
  - `Total Revenue`: `SUM(total_revenue)` — Format: `$#,##0.00`
  - `Average DAU`: `AVG(dau)` — Format: `,d`
  - `Average Order Value (AOV)`: `SUM(total_revenue) / SUM(total_orders)` — Format: `$#,##0.00`
  - `Overall CR`: `AVG(daily_conversion_rate_pct)` — Format: `.2f%`

### Chart 2: Conversion Funnel (Row 2, Left)
- **Dataset**: `v_funnel_summary`
- **Visualization Type**: Funnel Chart or Stepped Bar Chart
- **Metrics**:
  - Step 1: `SUM(view_users)` (Label: "1. View Product")
  - Step 2: `SUM(cart_users)` (Label: "2. Add to Cart")
  - Step 3: `SUM(purchase_users)` (Label: "3. Purchase")
- **Settings**: Show absolute numbers and relative step conversion rate percentages.

### Chart 3: Category Drop-off Rate Comparison (Row 2, Right)
- **Dataset**: `v_funnel_summary`
- **Visualization Type**: Grouped Bar Chart
- **X-Axis**: `top_category`
- **Y-Axis**: `AVG(dropoff_view_to_cart_pct)`, `AVG(dropoff_cart_to_purchase_pct)`
- **Color Palette**: Red-Orange gradient for friction highlighting.

### Chart 4: Cohort Retention Heatmap (Row 3)
- **Dataset**: `v_cohort_retention`
- **Visualization Type**: Pivot Table v2 or Heatmap Chart
- **Rows**: `cohort_week`
- **Columns**: `cohort_index` (Week 0, Week 1, Week 2, Week 3, Week 4...)
- **Metric**: `AVG(retention_rate_pct)`
- **Cell Formatting**: Color scale using `Blues` (0% pale blue to 100% deep blue), displaying `%` suffix.

### Chart 5: Category Treemap (Row 4, Left)
- **Dataset**: `v_funnel_summary`
- **Visualization Type**: Treemap
- **Hierarchy**: `top_category` $\rightarrow$ `brand`
- **Metric Size**: `SUM(purchase_users * 100)` (Proxy for Volume)
- **Metric Color**: `AVG(overall_cr_pct)`

---

## 4. Global Dashboard Filters & Jinja Templating

### Global Filter Slices:
1. **Time Grain & Range Filter**:
   - Filter Column: `event_date` (or `event_time`)
   - Default: `Last 30 Days`
2. **Top Category Filter**:
   - Filter Column: `top_category`
   - Select Type: Multi-select with Search
3. **Brand Filter**:
   - Filter Column: `brand`
   - Select Type: Multi-select with Search

### Jinja Template Filtering Syntax for Custom SQL Slices:
```sql
SELECT *
FROM v_funnel_summary
WHERE 1=1
  {% if filter_values('top_category') %}
    AND top_category IN ({{ "'" + "','".join(filter_values('top_category')) + "'" }})
  {% endif %}
  {% if filter_values('brand') %}
    AND brand IN ({{ "'" + "','".join(filter_values('brand')) + "'" }})
  {% endif %}
```
