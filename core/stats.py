"""Basic descriptive statistics for the data workspace."""

import pandas as pd


def dataset_summary(frame: pd.DataFrame) -> dict:
    brands = sorted(frame["brand"].dropna().astype(str).unique().tolist()) if "brand" in frame else []
    platforms = sorted(frame["platform"].dropna().astype(str).unique().tolist()) if "platform" in frame else []
    dates = frame["published_at"].dropna() if "published_at" in frame else pd.Series(dtype="datetime64[ns]")
    date_range = "未提供日期"
    if not dates.empty:
        date_range = f"{dates.min():%Y-%m-%d} 至 {dates.max():%Y-%m-%d}"
    return {
        "records": len(frame),
        "brands": brands,
        "brand_count": len(brands),
        "platforms": platforms,
        "date_range": date_range,
        "date_available": not dates.empty,
    }
