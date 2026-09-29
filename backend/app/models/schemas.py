"""Typed request/response models for the API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    medicine_id: str = Field(..., examples=["MED-001"])


class ApproveRequest(BaseModel):
    supplier_id: str | None = Field(None, description="Override the recommended supplier (modify)")
    quantity: int | None = Field(None, gt=0, le=100000, description="Override the recommended quantity (modify)")
    note: str | None = Field(None, max_length=500)


class RejectRequest(BaseModel):
    reason: str | None = Field(None, max_length=500)


class OutcomeRequest(BaseModel):
    delivered_quantity: int = Field(..., ge=0, le=100000)
    delivery_days: float = Field(..., gt=0, le=60)
    stockout_occurred: bool = False
    notes: str | None = Field(None, max_length=500)


class RecallRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=300)


class SettingsUpdate(BaseModel):
    expiry_threshold_days: int | None = Field(None, ge=7, le=365)
    target_cover_days: float | None = Field(None, ge=3, le=30)


class DemoRunRequest(BaseModel):
    action: Literal["prepare", "new_situation"] = "prepare"
    medicine_id: str = "MED-001"


class HealthResponse(BaseModel):
    database: dict[str, Any]
    agent: dict[str, Any]
    hindsight: dict[str, Any]
