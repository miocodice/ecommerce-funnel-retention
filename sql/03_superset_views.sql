-- =============================================================================
-- E-commerce Funnel & Retention Analysis
-- Step 4: Analytical Views for Apache Superset (PostgreSQL 15+)
-- =============================================================================
-- Author: Lead Data Engineer / Senior Product Analyst
-- Description: Production database views and materialized views optimized 
--              for Apache Superset BI dashboards and slices.
-- =============================================================================

--------------------------------------------------------------------------------
-- 1. View: v_kpi_daily (High-Level Executive Daily KPIs)
--------------------------------------------------------------------------------

CREATE OR REPLACE VIEW v_kpi_daily AS
WITH daily_metrics AS (
    SELECT
        DATE_TRUNC('day', event_time)::date AS event_date,
        COUNT(DISTINCT user_id) AS dau,
        COUNT(DISTINCT effective_session_id) AS total_sessions,
        COUNT(DISTINCT CASE WHEN event_type = 'purchase' THEN user_id END) AS purchasing_users,
        COUNT(CASE WHEN event_type = 'purchase' THEN 1 END) AS total_orders,
        COALESCE(SUM(CASE WHEN event_type = 'purchase' THEN price END), 0) AS total_revenue
    FROM v_events_sessionized
    GROUP BY DATE_TRUNC('day', event_time)::date
)
SELECT
    event_date,
    dau,
    total_sessions,
    purchasing_users,
    total_orders,
    ROUND(total_revenue::numeric, 2) AS total_revenue,
    -- Average Order Value (AOV = Revenue / Total Orders)
    ROUND((total_revenue / NULLIF(total_orders, 0))::numeric, 2) AS aov,
    -- Revenue Per Active User (ARPU = Revenue / DAU)
    ROUND((total_revenue / NULLIF(dau, 0))::numeric, 2) AS arpu,
    -- Daily Overall User Conversion Rate (%)
    ROUND((purchasing_users::numeric / NULLIF(dau, 0)) * 100, 2) AS daily_conversion_rate_pct
FROM daily_metrics;

COMMENT ON VIEW v_kpi_daily IS 'Daily executive KPIs: DAU, Revenue, Orders, AOV, ARPU, Overall Conversion Rate';

--------------------------------------------------------------------------------
-- 2. View: v_funnel_summary (Aggregated Funnel by Day, Category & Brand)
--------------------------------------------------------------------------------

CREATE OR REPLACE VIEW v_funnel_summary AS
WITH event_step_flags AS (
    SELECT
        DATE_TRUNC('day', event_time)::date AS event_date,
        COALESCE(SPLIT_PART(category_code, '.', 1), 'uncategorized') AS top_category,
        COALESCE(brand, 'unknown') AS brand,
        user_id,
        effective_session_id,
        MAX(CASE WHEN event_type = 'view' THEN 1 ELSE 0 END) AS has_view,
        MAX(CASE WHEN event_type = 'cart' THEN 1 ELSE 0 END) AS has_cart,
        MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS has_purchase
    FROM v_events_sessionized
    GROUP BY 
        DATE_TRUNC('day', event_time)::date,
        COALESCE(SPLIT_PART(category_code, '.', 1), 'uncategorized'),
        COALESCE(brand, 'unknown'),
        user_id,
        effective_session_id
),
aggregated_funnel AS (
    SELECT
        event_date,
        top_category,
        brand,
        COUNT(DISTINCT CASE WHEN has_view = 1 THEN user_id END) AS view_users,
        COUNT(DISTINCT CASE WHEN has_view = 1 AND has_cart = 1 THEN user_id END) AS cart_users,
        COUNT(DISTINCT CASE WHEN has_view = 1 AND has_cart = 1 AND has_purchase = 1 THEN user_id END) AS purchase_users,
        COUNT(DISTINCT CASE WHEN has_view = 1 THEN effective_session_id END) AS view_sessions,
        COUNT(DISTINCT CASE WHEN has_view = 1 AND has_cart = 1 THEN effective_session_id END) AS cart_sessions,
        COUNT(DISTINCT CASE WHEN has_view = 1 AND has_cart = 1 AND has_purchase = 1 THEN effective_session_id END) AS purchase_sessions
    FROM event_step_flags
    GROUP BY event_date, top_category, brand
)
SELECT
    event_date,
    top_category,
    brand,
    view_users,
    cart_users,
    purchase_users,
    view_sessions,
    cart_sessions,
    purchase_sessions,
    -- Step 1 to Step 2 CR & Drop-off
    ROUND((cart_users::numeric / NULLIF(view_users, 0)) * 100, 2) AS cr_view_to_cart_pct,
    ROUND(((view_users - cart_users)::numeric / NULLIF(view_users, 0)) * 100, 2) AS dropoff_view_to_cart_pct,
    -- Step 2 to Step 3 CR & Drop-off
    ROUND((purchase_users::numeric / NULLIF(cart_users, 0)) * 100, 2) AS cr_cart_to_purchase_pct,
    ROUND(((cart_users - purchase_users)::numeric / NULLIF(cart_users, 0)) * 100, 2) AS dropoff_cart_to_purchase_pct,
    -- Overall CR & Drop-off
    ROUND((purchase_users::numeric / NULLIF(view_users, 0)) * 100, 2) AS overall_cr_pct,
    ROUND(((view_users - purchase_users)::numeric / NULLIF(view_users, 0)) * 100, 2) AS overall_dropoff_pct
FROM aggregated_funnel;

COMMENT ON VIEW v_funnel_summary IS 'Daily aggregated conversion funnel breakdown by top category and brand';

--------------------------------------------------------------------------------
-- 3. View: v_cohort_retention (Flat Cohort Retention View for BI)
--------------------------------------------------------------------------------

CREATE OR REPLACE VIEW v_cohort_retention AS
WITH user_first_event AS (
    SELECT
        user_id,
        MIN(event_time) AS first_event_time,
        DATE_TRUNC('week', MIN(event_time))::date AS cohort_week
    FROM v_events_sessionized
    GROUP BY user_id
),
user_weekly_activity AS (
    SELECT DISTINCT
        e.user_id,
        f.cohort_week,
        DATE_TRUNC('week', e.event_time)::date AS activity_week,
        ROUND((EXTRACT(EPOCH FROM (DATE_TRUNC('week', e.event_time) - f.cohort_week)) / (7 * 86400))::numeric) AS cohort_index
    FROM v_events_sessionized e
    JOIN user_first_event f ON e.user_id = f.user_id
),
cohort_sizes AS (
    SELECT
        cohort_week,
        COUNT(DISTINCT user_id) AS cohort_size
    FROM user_first_event
    GROUP BY cohort_week
),
cohort_activity_counts AS (
    SELECT
        cohort_week,
        cohort_index,
        COUNT(DISTINCT user_id) AS active_users
    FROM user_weekly_activity
    GROUP BY cohort_week, cohort_index
)
SELECT
    a.cohort_week,
    'Week ' || a.cohort_index::text AS cohort_period_label,
    a.cohort_index,
    s.cohort_size,
    a.active_users,
    ROUND((a.active_users::numeric / NULLIF(s.cohort_size, 0)) * 100, 2) AS retention_rate_pct
FROM cohort_activity_counts a
JOIN cohort_sizes s ON a.cohort_week = s.cohort_week
ORDER BY a.cohort_week ASC, a.cohort_index ASC;

COMMENT ON VIEW v_cohort_retention IS 'Flat weekly cohort retention metrics for Superset Cohort / Heatmap charts';
