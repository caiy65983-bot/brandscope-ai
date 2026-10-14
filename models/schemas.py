"""Canonical input and AI annotation schemas."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FeedbackRecord(BaseModel):
    """One normalized consumer feedback row."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    record_id: Optional[str] = Field(default=None, description="Unique row identifier")
    brand: Optional[str] = Field(default=None, description="Brand discussed")
    platform: Optional[str] = Field(default=None, description="Source platform")
    published_at: Optional[str] = Field(default=None, description="Publication date")
    content: str = Field(min_length=1, description="Consumer text; required")
    content_type: Optional[str] = None
    likes: Optional[int] = Field(default=None, ge=0)
    source_id: Optional[str] = None
    source_url: Optional[str] = None


class Topic(str, Enum):
    PRICE = "价格与性价比"
    TASTE = "产品口味"
    FUNCTIONAL = "提神与功能性需求"
    HEALTH = "健康与低糖"
    SERVICE = "门店服务与便利性"
    LIFESTYLE = "社交与生活方式"
    BRAND = "品牌形象"
    OTHER = "其他"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class TextAnalysis(BaseModel):
    """Validated annotation. Evidence must be checked against the source text."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    record_id: str = Field(min_length=1)
    topics: List[Topic] = Field(default_factory=list)
    sentiment: Sentiment
    pain_points: List[str] = Field(default_factory=list)
    purchase_motivation: List[str] = Field(default_factory=list)
    scenarios: List[str] = Field(default_factory=list)
    evidence_text: str = Field(min_length=1)
    analysis_method: str = "llm"
    model_name: Optional[str] = None


class StrategyAdvice(BaseModel):
    """Qualitative model-authored advice, linked to source record IDs."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    topic: str = Field(min_length=1, max_length=80)
    recommendation: str = Field(min_length=1, max_length=500)
    scenario: str = Field(default="", max_length=160)
    message_direction: str = Field(default="", max_length=240)
    content_concept: str = Field(default="", max_length=300)
    verification_metrics: List[str] = Field(default_factory=list, max_length=5)
    evidence_ids: List[str] = Field(min_length=1, max_length=10)


class StrategyNarrative(BaseModel):
    """Optional AI narrative. Numeric facts remain outside this schema."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    executive_summary: str = Field(min_length=1, max_length=800)
    recommendations: List[StrategyAdvice] = Field(min_length=1, max_length=5)


CANONICAL_FIELDS = {
    "record_id": "记录编号", "brand": "品牌", "platform": "来源平台",
    "published_at": "发布日期", "content": "评论内容（必需）",
    "content_type": "内容类型", "likes": "点赞量", "source_id": "来源标识",
    "source_url": "来源链接",
}

FIELD_ALIASES = {
    "record_id": ("record_id", "id", "评论id", "记录编号", "记录id", "序号"),
    "brand": ("brand", "品牌", "品牌名称"),
    "platform": ("platform", "平台", "来源平台", "数据来源"),
    "published_at": ("published_at", "date", "日期", "发布时间", "发布日期", "时间"),
    "content": ("content", "text", "评论", "评论内容", "文本", "内容", "评价"),
    "content_type": ("content_type", "类型", "内容类型"),
    "likes": ("likes", "点赞", "点赞量", "互动量"),
    "source_id": ("source_id", "来源id", "来源标识"),
    "source_url": ("source_url", "链接", "来源链接", "url"),
}
