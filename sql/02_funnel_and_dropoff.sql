-- =============================================================================
-- E-commerce Funnel & Retention Analysis
-- Step 2: Funnel, Drop-off & Time-to-Buy (TTB) Calculation (PostgreSQL 15+)
-- =============================================================================
-- Author: Lead Data Engineer / Senior Product Analyst
-- Description: Advanced CTE and Window Function pipeline to calculate strict 
--              chronological conversion funnel: View -> Cart -> Purchase.
-- =============================================================================

--------------------------------------------------------------------------------
-- 1. Detailed Session-Level Funnel Step Order and TTB
--------------------------------------------------------------------------------

WITH session_event_timestamps AS (
    SELECT
        user_id,
        effective_session_id,
        -- Extract first event timestamp for each action in the session
        MIN(CASE WHEN event_type = 'view' THEN event_time END) AS min_view_time,
        MIN(CASE WHEN event_type = 'cart' THEN event_time END) AS min_cart_time,
        MIN(CASE WHEN event_type = 'purchase' THEN event_time END) AS min_purchase_time,
        -- Use Window Functions FIRST_VALUE to track initial and final event times in session
        FIRST_VALUE(event_time) OVER (
            PARTITION BY user_id, effective_session_id 
            ORDER BY event_time ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS session_start_time,
        LAST_VALUE(event_time) OVER (
            PARTITION BY user_id, effective_session_id 
            ORDER BY event_time ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS session_end_time
    FROM v_events_sessionized
    GROUP BY user_id, effective_session_id, event_time
),
session_funnel_flags AS (
    SELECT
        user_id,
        effective_session_id,
        min_view_time,
        min_cart_time,
        min_purchase_time,
        -- Strict Chronological Funnel Validation:
        -- Step 1 (View): Has at least one view event
        CASE WHEN min_view_time IS NOT NULL THEN 1 ELSE 0 END AS reached_view,
        
        -- Step 2 (Cart): Has cart event after or equal to view event
        CASE 
            WHEN min_view_time IS NOT NULL 
                 AND min_cart_time IS NOT NULL 
                 AND min_cart_time >= min_view_time 
            THEN 1 ELSE 0 
        END AS reached_cart,
        
        -- Step 3 (Purchase): Has purchase event after or equal to cart event
        CASE 
            WHEN min_view_time IS NOT NULL 
                 AND min_cart_time IS NOT NULL 
                 AND min_purchase_time IS NOT NULL 
                 AND min_cart_time >= min_view_time 
                 AND min_purchase_time >= min_cart_time 
            THEN 1 ELSE 0 
        END AS reached_purchase,

        -- TTB (Time-to-Buy) in seconds: difference between first view and first purchase in session
        CASE 
            WHEN min_view_time IS NOT NULL AND min_purchase_time IS NOT NULL 
                 AND min_purchase_time >= min_view_time
            THEN EXTRACT(EPOCH FROM (min_purchase_time - min_view_time))
            ELSE NULL 
        END AS ttb_seconds
    FROM session_event_timestamps
),
funnel_summary AS (
    SELECT
        -- Unique User Counts per Step
        COUNT(DISTINCT CASE WHEN reached_view = 1 THEN user_id END) AS step_1_view_users,
        COUNT(DISTINCT CASE WHEN reached_cart = 1 THEN user_id END) AS step_2_cart_users,
        COUNT(DISTINCT CASE WHEN reached_purchase = 1 THEN user_id END) AS step_3_purchase_users,
        
        -- Unique Session Counts per Step
        COUNT(DISTINCT CASE WHEN reached_view = 1 THEN effective_session_id END) AS step_1_view_sessions,
        COUNT(DISTINCT CASE WHEN reached_cart = 1 THEN effective_session_id END) AS step_2_cart_sessions,
        COUNT(DISTINCT CASE WHEN reached_purchase = 1 THEN effective_session_id END) AS step_3_purchase_sessions,

        -- Time to Buy (TTB) Aggregations
        ROUND(AVG(ttb_seconds)::numeric, 2) AS avg_ttb_seconds,
        ROUND((AVG(ttb_seconds) / 60.0)::numeric, 2) AS avg_ttb_minutes,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ttb_seconds) AS median_ttb_seconds,
        ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ttb_seconds) / 60.0)::numeric, 2) AS median_ttb_minutes
    FROM session_funnel_flags
)
SELECT
    -- Absolute Counts
    step_1_view_users,
    step_2_cart_users,
    step_3_purchase_users,

    -- Conversion Rates (CR %)
    ROUND((step_2_cart_users::numeric / NULLIF(step_1_view_users, 0)) * 100, 2) AS cr_view_to_cart_pct,
    ROUND((step_3_purchase_users::numeric / NULLIF(step_2_cart_users, 0)) * 100, 2) AS cr_cart_to_purchase_pct,
    ROUND((step_3_purchase_users::numeric / NULLIF(step_1_view_users, 0)) * 100, 2) AS overall_conversion_rate_pct,

    -- Drop-off Rates (% loss at each stage)
    ROUND(((step_1_view_users - step_2_cart_users)::numeric / NULLIF(step_1_view_users, 0)) * 100, 2) AS dropoff_view_to_cart_pct,
    ROUND(((step_2_cart_users - step_3_purchase_users)::numeric / NULLIF(step_2_cart_users, 0)) * 100, 2) AS dropoff_cart_to_purchase_pct,
    ROUND(((step_1_view_users - step_3_purchase_users)::numeric / NULLIF(step_1_view_users, 0)) * 100, 2) AS overall_dropoff_rate_pct,

    -- TTB Metrics
    avg_ttb_minutes,
    median_ttb_minutes
FROM funnel_summary;
