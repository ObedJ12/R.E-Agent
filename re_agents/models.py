"""Shared data shapes passed between agents."""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class Condition(int, Enum):
    """Appraiser-style condition scale (C1 = new, C6 = severe damage)."""

    C1 = 1
    C2 = 2
    C3 = 3
    C4 = 4
    C5 = 5
    C6 = 6


class Property(BaseModel):
    address: str
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    property_type: str | None = None
    bedrooms: float | None = None
    bathrooms: float | None = None
    square_footage: float | None = None
    lot_size: float | None = None
    year_built: int | None = None
    last_sale_date: date | None = None
    last_sale_price: float | None = None


class Comp(Property):
    price: float
    status: str | None = None  # "Active" listing or "Inactive" (removed, usually sold)
    listed_date: date | None = None
    removed_date: date | None = None
    days_on_market: int | None = None
    distance_miles: float | None = None
    days_old: int | None = None
    correlation: float | None = None  # vendor similarity score 0..1


class AdjustedComp(BaseModel):
    comp: Comp
    adjustments: dict[str, float] = Field(default_factory=dict)
    adjusted_price: float
    weight: float
    excluded_reason: str | None = None

    @property
    def total_adjustment(self) -> float:
        return sum(self.adjustments.values())


class Valuation(BaseModel):
    as_is_value: float
    arv: float
    low: float
    high: float
    distressed_value: float | None = None
    price_per_sqft: float | None
    comps_used: list[AdjustedComp]
    comps_excluded: list[AdjustedComp] = Field(default_factory=list)
    confidence: str  # "high" | "medium" | "low"
    notes: list[str] = Field(default_factory=list)


class RepairLine(BaseModel):
    item: str
    cost: float
    note: str = ""


class RepairEstimate(BaseModel):
    condition: Condition
    scope: str  # "cosmetic" | "moderate" | "full gut"
    lines: list[RepairLine]
    contingency_pct: float = 0.10

    @property
    def subtotal(self) -> float:
        return sum(line.cost for line in self.lines)

    @property
    def total(self) -> float:
        return round(self.subtotal * (1 + self.contingency_pct), -2)
