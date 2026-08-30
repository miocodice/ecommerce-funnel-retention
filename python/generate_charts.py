"""
Chart and Screenshot Generator for E-Commerce Funnel & Retention Analysis
Generates high-resolution PNG charts for README documentation.
"""

import os
import polars as pl
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns

# Set style aesthetics
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 11

def generate_cohort_heatmap(parquet_path: str, output_path: str):
    """Generates a polished cohort retention heatmap PNG."""
    lf = pl.scan_parquet(parquet_path)
    
    # 1. First activity per user
    user_first = lf.group_by("user_id").agg(pl.col("event_time").min().alias("first_event_time"))
    events = lf.join(user_first, on="user_id", how="inner")
    
    # 2. Weekly cohort
    events = events.with_columns([
        pl.col("first_event_time").dt.truncate("1w").dt.strftime("%Y-W%V").alias("cohort_group"),
        pl.col("event_time").dt.truncate("1w").dt.strftime("%Y-W%V").alias("event_period"),
        ((pl.col("event_time").dt.truncate("1w") - pl.col("first_event_time").dt.truncate("1w")).dt.total_days() // 7).cast(pl.Int64).alias("cohort_index")
    ])
    
    # 3. Aggregations
    cohort_counts = (
        events.group_by(["cohort_group", "cohort_index"])
        .agg(pl.col("user_id").n_unique().alias("active_users"))
        .sort(["cohort_group", "cohort_index"])
        .collect()
    )
    
    cohort_sizes = (
        cohort_counts.filter(pl.col("cohort_index") == 0)
        .select([pl.col("cohort_group"), pl.col("active_users").alias("cohort_size")])
    )
    
    flat_df = (
        cohort_counts.join(cohort_sizes, on="cohort_group", how="left")
        .with_columns([
            (pl.col("active_users") / pl.col("cohort_size") * 100.0).round(1).alias("retention_rate")
        ])
    )
    
    retention_pivot = (
        flat_df.pivot(on="cohort_index", index="cohort_group", values="retention_rate")
        .sort("cohort_group")
        .to_pandas()
        .set_index("cohort_group")
    )
    
    sizes_dict = cohort_sizes.to_pandas().set_index("cohort_group")["cohort_size"].to_dict()
    y_labels = [f"{grp}  (N={sizes_dict.get(grp, 0)})" for grp in retention_pivot.index]
    x_labels = [f"Week {c}" for c in retention_pivot.columns]
    
    # Plotting
    fig, ax = plt.subplots(figsize=(12, 7), dpi=300)
    
    cmap = sns.light_palette("#1E40AF", as_cmap=True) # Deep modern blue
    
    sns.heatmap(
        retention_pivot,
        annot=True,
        fmt=".1f",
        cmap=cmap,
        linewidths=1.2,
        linecolor="#F1F5F9",
        cbar_kws={'label': 'User Retention Rate (%)', 'shrink': 0.8},
        yticklabels=y_labels,
        xticklabels=x_labels,
        vmin=0,
        vmax=100,
        ax=ax
    )
    
    ax.set_title("Weekly Cohort User Retention Rate (%)", fontsize=16, fontweight="bold", pad=20, color="#0F172A")
    ax.set_xlabel("Elapsed Timeline (Weeks since first visit)", fontsize=12, fontweight="600", labelpad=12, color="#334155")
    ax.set_ylabel("Cohort Group (First Visit Week)", fontsize=12, fontweight="600", labelpad=12, color="#334155")
    plt.xticks(rotation=0)
    plt.yticks(rotation=0)
    plt.tight_layout()
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved cohort heatmap to: {output_path}")

def generate_funnel_chart(parquet_path: str, output_path: str):
    """Generates a funnel and drop-off chart."""
    lf = pl.scan_parquet(parquet_path)
    df = lf.collect()
    
    # Session counts per step
    views_users = df.filter(pl.col("event_type") == "view")["user_id"].n_unique()
    cart_users = df.filter(pl.col("event_type") == "cart")["user_id"].n_unique()
    purchase_users = df.filter(pl.col("event_type") == "purchase")["user_id"].n_unique()
    
    stages = ["1. Product Views", "2. Cart Additions", "3. Completed Purchases"]
    counts = [views_users, cart_users, purchase_users]
    
    cr_1_to_2 = (cart_users / views_users) * 100
    cr_2_to_3 = (purchase_users / cart_users) * 100
    overall_cr = (purchase_users / views_users) * 100
    
    drop_1_to_2 = 100 - cr_1_to_2
    drop_2_to_3 = 100 - cr_2_to_3
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=300, gridspec_kw={'width_ratios': [1.8, 1]})
    
    # Horizontal bar funnel
    colors = ["#3B82F6", "#06B6D4", "#10B981"]
    bars = ax1.barh(stages, counts, color=colors, height=0.55, edgecolor="#0F172A", linewidth=1)
    ax1.invert_yaxis()
    ax1.set_title("E-Commerce Conversion Funnel (Unique Users)", fontsize=15, fontweight="bold", pad=15, color="#0F172A")
    ax1.set_xlabel("Unique Users", fontsize=11, fontweight="600", color="#334155")
    ax1.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f"{int(x):,}"))
    
    for bar, count in zip(bars, counts):
        ax1.text(
            bar.get_width() + 15,
            bar.get_y() + bar.get_height()/2,
            f"{count:,} users",
            va='center', ha='left', fontsize=11, fontweight='bold', color="#0F172A"
        )
    ax1.set_xlim(0, max(counts) * 1.25)
    
    # Conversion & Drop-off summary table/cards
    ax2.axis('off')
    ax2.set_title("Step Conversion & Friction Summary", fontsize=14, fontweight="bold", pad=15, color="#0F172A")
    
    card_data = [
        ("View → Cart Conversion Rate", f"{cr_1_to_2:.1f}%", f"Drop-off: -{drop_1_to_2:.1f}%", "#3B82F6", "#EF4444"),
        ("Cart → Purchase Conversion Rate", f"{cr_2_to_3:.1f}%", f"Drop-off: -{drop_2_to_3:.1f}%", "#06B6D4", "#EF4444"),
        ("Overall Funnel Conversion (CR)", f"{overall_cr:.1f}%", f"Total Drop: -{100-overall_cr:.1f}%", "#10B981", "#64748B")
    ]
    
    y_pos = 0.8
    for title, metric, drop, color_m, color_d in card_data:
        # Draw bounding card
        from matplotlib.patches import FancyBboxPatch
        bbox = FancyBboxPatch((0.02, y_pos - 0.2), 0.96, 0.22, transform=ax2.transAxes,
                              boxstyle="round,pad=0.03", facecolor="#F8FAFC", edgecolor="#CBD5E1", linewidth=1.5)
        ax2.add_patch(bbox)
        
        ax2.text(0.06, y_pos - 0.04, title, transform=ax2.transAxes, fontsize=11, fontweight='600', color="#334155")
        ax2.text(0.06, y_pos - 0.15, metric, transform=ax2.transAxes, fontsize=16, fontweight='bold', color=color_m)
        ax2.text(0.55, y_pos - 0.15, drop, transform=ax2.transAxes, fontsize=12, fontweight='bold', color=color_d)
        
        y_pos -= 0.3
        
    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved funnel chart to: {output_path}")

def generate_kpi_trends(parquet_path: str, output_path: str):
    """Generates daily KPI trends (DAU, Revenue, AOV)."""
    lf = pl.scan_parquet(parquet_path)
    
    daily = (
        lf.with_columns(pl.col("event_time").dt.truncate("1d").alias("event_date"))
        .group_by("event_date")
        .agg([
            pl.col("user_id").n_unique().alias("dau"),
            pl.col("price").filter(pl.col("event_type") == "purchase").sum().alias("revenue"),
            (pl.col("event_type") == "purchase").sum().alias("orders")
        ])
        .with_columns([
            (pl.col("revenue") / pl.col("orders")).alias("aov")
        ])
        .sort("event_date")
        .collect()
        .to_pandas()
    )
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 7), sharex=True, dpi=300)
    
    # 1. Daily Active Users (DAU) & Orders
    ax1.plot(daily["event_date"], daily["dau"], color="#3B82F6", linewidth=2.2, label="Daily Active Users (DAU)")
    ax1.fill_between(daily["event_date"], daily["dau"], color="#3B82F6", alpha=0.15)
    ax1.set_title("E-Commerce Executive Daily KPI Trends", fontsize=15, fontweight="bold", pad=12, color="#0F172A")
    ax1.set_ylabel("DAU", fontsize=11, fontweight="600", color="#334155")
    ax1.legend(loc="upper left", frameon=True)
    ax1.grid(True, linestyle="--", alpha=0.6)
    
    # 2. Daily Revenue & AOV
    ax2.plot(daily["event_date"], daily["revenue"], color="#10B981", linewidth=2.2, label="Daily Revenue ($)")
    ax2.fill_between(daily["event_date"], daily["revenue"], color="#10B981", alpha=0.15)
    ax2.set_ylabel("Revenue ($)", fontsize=11, fontweight="600", color="#334155")
    ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f"${int(x):,}"))
    ax2.set_xlabel("Date", fontsize=11, fontweight="600", color="#334155")
    ax2.legend(loc="upper left", frameon=True)
    ax2.grid(True, linestyle="--", alpha=0.6)
    
    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved KPI trend chart to: {output_path}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(base_dir, "..")
    parquet_file = os.path.join(project_root, "data", "sample_raw_events.parquet")
    images_dir = os.path.join(project_root, "docs", "images")
    
    print("Generating chart images for documentation...")
    generate_cohort_heatmap(parquet_file, os.path.join(images_dir, "cohort_retention_heatmap.png"))
    generate_funnel_chart(parquet_file, os.path.join(images_dir, "conversion_funnel.png"))
    generate_kpi_trends(parquet_file, os.path.join(images_dir, "daily_kpi_trends.png"))
    print("All charts generated successfully.")
