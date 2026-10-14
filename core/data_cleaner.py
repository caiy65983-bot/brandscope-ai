"""Deterministic cleaning rules and an auditable cleaning summary."""

from typing import Dict, Tuple

import pandas as pd

from core.data_loader import apply_mapping


def clean_feedback(frame: pd.DataFrame, mapping: Dict[str, str]) -> Tuple[pd.DataFrame, dict]:
    """Normalize mapped input. Rows without text are excluded; invalid dates are retained as missing."""
    normalized = apply_mapping(frame, mapping)
    # Preserve only the two explicitly simulated annotation fields for the demo dataset.
    for demo_field in ("demo_topic", "demo_sentiment"):
        if demo_field in frame.columns:
            normalized[demo_field] = frame[demo_field]
    before = len(normalized)
    logs = []

    content = normalized["content"].astype("string").str.replace(r"\s+", " ", regex=True).str.strip()
    missing_content = content.isna() | content.eq("")
    removed_empty = int(missing_content.sum())
    normalized = normalized.loc[~missing_content].copy()
    normalized["content"] = content.loc[~missing_content]
    if removed_empty:
        logs.append({"项目": "空评论", "数量": removed_empty, "处理": "剔除（评论内容为必需字段）"})

    for field in ("record_id", "brand", "platform", "content_type", "source_id", "source_url"):
        normalized[field] = normalized[field].astype("string").str.strip().replace("", pd.NA)

    date_raw = normalized["published_at"].astype("string").str.strip().replace("", pd.NA)
    parsed_dates = pd.to_datetime(date_raw, errors="coerce", format="mixed", utc=True)
    # format="mixed" is supported by pandas 2.x; retain fallback for older installations.
    normalized["published_at"] = parsed_dates.dt.tz_convert(None)
    invalid_dates = int((date_raw.notna() & normalized["published_at"].isna()).sum())
    if invalid_dates:
        logs.append({"项目": "日期格式异常", "数量": invalid_dates, "处理": "保留记录，日期置空"})

    likes_raw = normalized["likes"].astype("string").str.replace(",", "", regex=False).str.strip()
    normalized["likes"] = pd.to_numeric(likes_raw, errors="coerce").astype("Int64")
    invalid_likes = int((likes_raw.notna() & likes_raw.ne("") & normalized["likes"].isna()).sum())
    negative_likes = normalized["likes"].lt(0).fillna(False)
    if negative_likes.any():
        invalid_likes += int(negative_likes.sum())
        normalized.loc[negative_likes, "likes"] = pd.NA
    if invalid_likes:
        logs.append({"项目": "点赞量异常", "数量": invalid_likes, "处理": "保留记录，非法或负数点赞量置空"})

    has_id = normalized["record_id"].notna()
    duplicate_mask = pd.Series(False, index=normalized.index)
    duplicate_mask.loc[has_id] = normalized.loc[has_id, "record_id"].duplicated(keep="first")
    missing_id_rows = normalized.loc[~has_id]
    duplicate_mask.loc[~has_id] = missing_id_rows.duplicated(
        subset=["brand", "published_at", "content"], keep="first"
    )
    duplicates = int(duplicate_mask.sum())
    normalized = normalized.loc[~duplicate_mask].reset_index(drop=True)
    if duplicates:
        logs.append({"项目": "重复记录", "数量": duplicates, "处理": "保留首条，剔除后续重复"})

    for field in ("brand", "platform"):
        missing = int(normalized[field].isna().sum())
        if missing:
            logs.append({"项目": f"缺失{field}", "数量": missing, "处理": "保留记录；对应分组分析不可用"})
    if not logs:
        logs.append({"项目": "数据检查", "数量": 0, "处理": "未发现需要处理的问题"})

    summary = {
        "rows_before": before,
        "rows_after": len(normalized),
        "removed": before - len(normalized),
        "logs": logs,
    }
    return normalized, summary
