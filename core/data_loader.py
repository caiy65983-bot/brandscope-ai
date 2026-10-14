"""CSV parsing and automatic field matching."""

from __future__ import annotations

from io import BytesIO
from typing import Dict, Tuple

import pandas as pd

from models.schemas import FIELD_ALIASES


def load_csv(file_bytes: bytes) -> Tuple[pd.DataFrame, str]:
    """Read CSV bytes with common Chinese CSV encodings."""
    if not file_bytes:
        raise ValueError("CSV 文件为空。")
    errors = []
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            frame = pd.read_csv(BytesIO(file_bytes), encoding=encoding, dtype=str, keep_default_na=False)
            if len(frame.columns) == 0:
                raise ValueError("没有识别到表头。")
            frame.columns = [str(column).strip() for column in frame.columns]
            return frame, encoding
        except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
            errors.append(f"{encoding}: {exc}")
    raise ValueError("无法读取 CSV。请检查文件编码和分隔符。" + "；".join(errors))


def suggest_mapping(columns) -> Dict[str, str]:
    """Match canonical fields using case-insensitive aliases; unmatched fields are empty."""
    normalized = {str(column).strip().casefold(): str(column) for column in columns}
    result = {}
    for field, aliases in FIELD_ALIASES.items():
        result[field] = next((normalized[a.casefold()] for a in aliases if a.casefold() in normalized), "")
    return result


def apply_mapping(frame: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
    """Return a copy with recognized source columns renamed to canonical names."""
    selected = {}
    for canonical, source in mapping.items():
        if source and source in frame.columns:
            selected[source] = canonical
    renamed = frame.loc[:, list(selected)].rename(columns=selected).copy()
    for canonical in FIELD_ALIASES:
        if canonical not in renamed.columns:
            renamed[canonical] = pd.NA
    return renamed
