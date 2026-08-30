"""
E-commerce Cohort Retention Analysis Engine (Polars + Plotly)
=============================================================================
Author: Lead Data Engineer / Senior Product Analyst
Description: Production-ready Python script performing Cohort Retention analysis 
              using Polars streaming API for high-performance memory efficiency 
              and generating interactive Plotly heatmaps.
=============================================================================
"""

import os
import sys
import argparse
from typing import Tuple, Optional
import polars as pl
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Configure Polars table formatting for Windows console compatibility
pl.Config.set_ascii_tables(True)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

class CohortRetentionAnalyzer:
    def __init__(self, granularity: str = "W"):
        """
        :param granularity: Cohort group granularity. 'W' for Weekly, 'M' for Monthly, 'D' for Daily.
        """
        if granularity.upper() not in ["D", "W", "M"]:
            raise ValueError("Granularity must be 'D' (Daily), 'W' (Weekly), or 'M' (Monthly)")
        self.granularity = granularity.upper()

    def load_data(self, file_path: str) -> pl.LazyFrame:
        """
        Loads dataset lazily using Polars to support multi-gigabyte clickstream files.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if file_path.endswith(".parquet"):
            lf = pl.scan_parquet(file_path)
        elif file_path.endswith(".csv"):
            lf = pl.scan_csv(
                file_path,
                try_parse_dates=True
            )
        else:
            raise ValueError("Unsupported file format. Supported formats: .parquet, .csv")

        return lf

    def calculate_cohort_retention(
        self, 
        lf: pl.LazyFrame,
        event_filter: Optional[str] = None
    ) -> Tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
        """
        Calculates cohort matrix for active users and retention rates.

        :param lf: Polars LazyFrame containing raw events.
        :param event_filter: Optional filter, e.g., 'purchase' for Buyer Retention.
        :return: (cohort_counts_matrix, retention_rate_matrix, flat_cohort_df)
        """
        # Step 0: Filter by event type if specified
        if event_filter:
            lf = lf.filter(pl.col("event_type") == event_filter)

        # Parse event_time to Datetime if string
        schema = lf.collect_schema()
        if schema["event_time"] == pl.Utf8:
            lf = lf.with_columns(
                pl.col("event_time").str.to_datetime()
            )

        # Step 1: Define Cohort Group (First Activity per user)
        user_first_activity = (
            lf.group_by("user_id")
            .agg(pl.col("event_time").min().alias("first_event_time"))
        )

        # Join first event time back to events
        events_with_first = lf.join(user_first_activity, on="user_id", how="inner")

        # Step 2: Format Cohort Group and Event Period dates according to granularity
        if self.granularity == "W":
            events_processed = events_with_first.with_columns([
                pl.col("first_event_time").dt.truncate("1w").dt.strftime("%Y-W%V").alias("cohort_group"),
                pl.col("event_time").dt.truncate("1w").dt.strftime("%Y-W%V").alias("event_period"),
                ((pl.col("event_time").dt.truncate("1w") - pl.col("first_event_time").dt.truncate("1w")).dt.total_days() // 7).cast(pl.Int64).alias("cohort_index")
            ])
        elif self.granularity == "M":
            events_processed = events_with_first.with_columns([
                pl.col("first_event_time").dt.strftime("%Y-%m").alias("cohort_group"),
                pl.col("event_time").dt.strftime("%Y-%m").alias("event_period"),
                (
                    (pl.col("event_time").dt.year() - pl.col("first_event_time").dt.year()) * 12 +
                    (pl.col("event_time").dt.month() - pl.col("first_event_time").dt.month())
                ).cast(pl.Int64).alias("cohort_index")
            ])
        else: # Daily
            events_processed = events_with_first.with_columns([
                pl.col("first_event_time").dt.strftime("%Y-%m-%d").alias("cohort_group"),
                pl.col("event_time").dt.strftime("%Y-%m-%d").alias("event_period"),
                ((pl.col("event_time") - pl.col("first_event_time")).dt.total_days()).cast(pl.Int64).alias("cohort_index")
            ])

        # Step 3: Aggregate unique active users per (cohort_group, cohort_index)
        cohort_counts = (
            events_processed
            .group_by(["cohort_group", "cohort_index"])
            .agg(pl.col("user_id").n_unique().alias("active_users"))
            .sort(["cohort_group", "cohort_index"])
            .collect()
        )

        # Step 4: Extract initial cohort sizes (Cohort Index 0)
        cohort_sizes = (
            cohort_counts
            .filter(pl.col("cohort_index") == 0)
            .select([pl.col("cohort_group"), pl.col("active_users").alias("cohort_size")])
        )

        # Join initial size to calculate Retention Rate
        flat_cohort_df = (
            cohort_counts
            .join(cohort_sizes, on="cohort_group", how="left")
            .with_columns([
                (pl.col("active_users") / pl.col("cohort_size") * 100.0).round(2).alias("retention_rate")
            ])
        )

        # Step 5: Pivot into Cohort Matrices
        counts_matrix = (
            flat_cohort_df
            .pivot(on="cohort_index", index="cohort_group", values="active_users")
            .sort("cohort_group")
        )

        retention_matrix = (
            flat_cohort_df
            .pivot(on="cohort_index", index="cohort_group", values="retention_rate")
            .sort("cohort_group")
        )

        return counts_matrix, retention_matrix, flat_cohort_df

    def render_interactive_heatmap(
        self, 
        retention_matrix: pl.DataFrame, 
        flat_cohort_df: pl.DataFrame,
        output_html_path: str
    ) -> go.Figure:
        """
        Renders an interactive Plotly heatmap with custom aesthetics and percentage annotations.
        """
        # Convert Polars DataFrame to Pandas for Plotly rendering
        df_pd = retention_matrix.to_pandas().set_index("cohort_group")
        
        # Build Cohort Size annotations for row labels
        cohort_sizes_dict = (
            flat_cohort_df
            .filter(pl.col("cohort_index") == 0)
            .select(["cohort_group", "cohort_size"])
            .to_pandas()
            .set_index("cohort_group")["cohort_size"]
            .to_dict()
        )
        
        y_labels = [f"{grp} (N={cohort_sizes_dict.get(grp, 0)})" for grp in df_pd.index]
        x_labels = [f"Period {col}" for col in df_pd.columns]

        # Text annotations matrix
        text_matrix = []
        for grp in df_pd.index:
            row_text = []
            for col in df_pd.columns:
                val = df_pd.loc[grp, col]
                if pd.isna(val):
                    row_text.append("")
                else:
                    row_text.append(f"{val:.1f}%")
            text_matrix.append(row_text)

        fig = go.Figure(
            data=go.Heatmap(
                z=df_pd.values,
                x=x_labels,
                y=y_labels,
                text=text_matrix,
                texttemplate="%{text}",
                textfont={"size": 11, "family": "Inter, sans-serif"},
                colorscale="Blues",
                showscale=True,
                colorbar=dict(title="Retention Rate (%)", ticksuffix="%"),
                hoverongaps=False
            )
        )

        fig.update_layout(
            title=dict(
                text=f"<b>Cohort Retention Rate Matrix ({'Weekly' if self.granularity == 'W' else 'Monthly'})</b>",
                x=0.02,
                font=dict(size=18, family="Inter, sans-serif")
            ),
            xaxis=dict(title="Cohort Period (Elapsed Units)", tickmode="linear"),
            yaxis=dict(title="Cohort Group (Initial Active Week/Month)", autorange="reversed"),
            template="plotly_white",
            height=600,
            width=1000,
            margin=dict(l=150, r=50, t=80, b=80)
        )

        # Create target directory if needed
        os.makedirs(os.path.dirname(output_html_path), exist_ok=True)
        fig.write_html(output_html_path)
        print(f"Saved interactive heatmap HTML to: {output_html_path}")
        return fig

def main():
    parser = argparse.ArgumentParser(description="E-commerce Cohort Retention Analysis")
    parser.add_argument("--input", type=str, default="data/sample_raw_events.parquet", help="Path to input parquet/csv")
    parser.add_argument("--granularity", type=str, default="W", choices=["D", "W", "M"], help="Retention period granularity")
    parser.add_argument("--output_html", type=str, default="docs/cohort_retention_heatmap.html", help="Path to save output heatmap HTML")
    parser.add_argument("--event_type", type=str, default=None, help="Filter by event type (e.g. purchase)")
    args = parser.parse_args()

    print(f"Initializing Cohort Retention Analyzer (Granularity: {args.granularity})...")
    analyzer = CohortRetentionAnalyzer(granularity=args.granularity)
    
    lf = analyzer.load_data(args.input)
    
    print("Calculating cohort metrics with Polars...")
    counts_mat, retention_mat, flat_df = analyzer.calculate_cohort_retention(lf, event_filter=args.event_type)

    print("\n--- Retention Rate Matrix (%) ---")
    print(retention_mat)

    print("\nRendering Plotly Heatmap...")
    analyzer.render_interactive_heatmap(retention_mat, flat_df, args.output_html)

if __name__ == "__main__":
    main()
