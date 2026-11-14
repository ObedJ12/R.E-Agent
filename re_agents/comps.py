"""Comp selection, adjustment and valuation.

Approach (a simplified version of what an appraiser does):
1. Drop comps that are too different (size, beds, age, distance, stale).
2. Adjust each remaining comp's price toward the subject: sqft, beds, baths, age.
3. Weight comps by closeness (distance, recency, similarity, closed vs active).
4. Split comps into renovated/retail and distressed groups at the biggest gap
   in adjusted $/sqft. ARV = weighted average of the retail group (or the top
   half when there is no clear gap).
5. As-is = ARV minus repairs, blended with the distressed comps when present.
"""

from __future__ import annotations

import statistics

from pydantic import BaseModel

from re_agents.models import AdjustedComp, Comp, Property, Valuation


class CompRules(BaseModel):
    max_distance_miles: float = 1.0
    max_days_old: int = 180
    max_sqft_diff_pct: float = 0.25
    max_bed_diff: float = 1
    max_year_diff: int = 25
    # Adjustment rates; tune to your market.
    per_bed: float = 7500
    per_full_bath: float = 6000
    per_year_age: float = 250
    sqft_rate_share: float = 0.5  # adjust sqft at half the comps' $/sqft (diminishing value)
    max_total_adjustment_pct: float = 0.25
    include_active_listings: bool = False
    distressed_gap_pct: float = 0.15  # $/sqft jump that separates as-is sales from renovated ones


def _filter(subject: Property, comp: Comp, rules: CompRules) -> str | None:
    if comp.distance_miles is not None and comp.distance_miles > rules.max_distance_miles:
        return f"{comp.distance_miles:.2f} mi away"
    if comp.days_old is not None and comp.days_old > rules.max_days_old:
        return f"{comp.days_old} days old"
    if not rules.include_active_listings and (comp.status or "").lower() == "active":
        return "still an active listing"
    if subject.square_footage and comp.square_footage:
        diff = abs(comp.square_footage - subject.square_footage) / subject.square_footage
        if diff > rules.max_sqft_diff_pct:
            return f"size differs {diff:.0%}"
    if subject.bedrooms is not None and comp.bedrooms is not None:
        if abs(comp.bedrooms - subject.bedrooms) > rules.max_bed_diff:
            return "bedroom count too different"
    if subject.year_built and comp.year_built:
        if abs(comp.year_built - subject.year_built) > rules.max_year_diff:
            return f"built {comp.year_built} vs {subject.year_built}"
    return None


def _weight(comp: Comp, rules: CompRules) -> float:
    w = 1.0
    if comp.distance_miles is not None:
        w *= max(0.2, 1 - comp.distance_miles / (rules.max_distance_miles * 1.25))
    if comp.days_old is not None:
        w *= max(0.3, 1 - comp.days_old / (rules.max_days_old * 1.5))
    if comp.correlation is not None:
        w *= max(0.3, comp.correlation)
    if (comp.status or "").lower() == "active":
        w *= 0.5  # asking price, not a sale
    return round(w, 4)


def adjust(subject: Property, comp: Comp, market_ppsf: float, rules: CompRules) -> AdjustedComp:
    adj: dict[str, float] = {}
    if subject.square_footage and comp.square_footage:
        adj["sqft"] = (subject.square_footage - comp.square_footage) * market_ppsf * rules.sqft_rate_share
    if subject.bedrooms is not None and comp.bedrooms is not None:
        adj["beds"] = (subject.bedrooms - comp.bedrooms) * rules.per_bed
    if subject.bathrooms is not None and comp.bathrooms is not None:
        adj["baths"] = (subject.bathrooms - comp.bathrooms) * rules.per_full_bath
    if subject.year_built and comp.year_built:
        adj["age"] = (subject.year_built - comp.year_built) * rules.per_year_age
    adj = {k: round(v) for k, v in adj.items() if round(v) != 0}

    cap = comp.price * rules.max_total_adjustment_pct
    total = sum(adj.values())
    if abs(total) > cap:
        scale = cap / abs(total)
        adj = {k: round(v * scale) for k, v in adj.items()}

    return AdjustedComp(
        comp=comp,
        adjustments=adj,
        adjusted_price=round(comp.price + sum(adj.values())),
        weight=_weight(comp, rules),
    )


def _weighted_median(values: list[tuple[float, float]]) -> float:
    ordered = sorted(values)
    total = sum(w for _, w in ordered)
    running = 0.0
    for value, w in ordered:
        running += w
        if running >= total / 2:
            return value
    return ordered[-1][0]


def _weighted_mean(values: list[tuple[float, float]]) -> float:
    total = sum(w for _, w in values)
    return sum(v * w for v, w in values) / total


def value_property(
    subject: Property,
    comps: list[Comp],
    rules: CompRules | None = None,
    repairs_total: float = 0.0,
    subject_needs_work: bool = True,
) -> Valuation:
    """repairs_total: rehab cost to bring the subject to renovated condition."""
    rules = rules or CompRules()
    kept: list[Comp] = []
    excluded: list[AdjustedComp] = []
    for c in comps:
        reason = _filter(subject, c, rules)
        if reason:
            excluded.append(AdjustedComp(comp=c, adjusted_price=c.price, weight=0, excluded_reason=reason))
        else:
            kept.append(c)

    if not kept:
        raise ValueError(
            "No usable comps after filtering. Widen the radius or time window, or include active listings."
        )

    ppsf = [c.price / c.square_footage for c in kept if c.square_footage]
    market_ppsf = statistics.median(ppsf) if ppsf else 0.0
    adjusted = [adjust(subject, c, market_ppsf, rules) for c in kept]

    # Split comps into a renovated/retail group and a distressed group at the
    # biggest jump in adjusted $/sqft (if the jump is big enough to be real).
    def adj_ppsf(a: AdjustedComp) -> float:
        return a.adjusted_price / (subject.square_footage or a.comp.square_footage or 1)

    ordered = sorted(adjusted, key=adj_ppsf)
    split = 0
    if len(ordered) >= 3:
        jumps = [(adj_ppsf(ordered[i + 1]) / adj_ppsf(ordered[i]) - 1, i + 1) for i in range(len(ordered) - 1)]
        best_jump, best_idx = max(jumps)
        if best_jump >= rules.distressed_gap_pct:
            split = best_idx
    distressed, retail = ordered[:split], ordered[split:]
    if not distressed:
        retail = ordered[len(ordered) // 2:]  # no clear gap: ARV from the top half

    arv = _weighted_mean([(a.adjusted_price, a.weight) for a in retail])
    distressed_value = _weighted_median([(a.adjusted_price, a.weight) for a in distressed]) if distressed else None

    # As-is: what the house is worth in its current condition.
    as_is = arv - repairs_total
    notes: list[str] = []
    if distressed_value is not None:
        notes.append(f"{len(distressed)} comp(s) look distressed/as-is (around ${distressed_value:,.0f}).")
        if repairs_total:
            as_is = (as_is + distressed_value) / 2
        else:
            as_is = distressed_value if subject_needs_work else arv
    as_is = min(as_is, arv)

    prices = [a.adjusted_price for a in retail]
    if len(retail) >= 4 and statistics.pstdev(prices) / statistics.mean(prices) < 0.10:
        confidence = "high"
    elif len(retail) >= 2:
        confidence = "medium"
    else:
        confidence = "low"
        notes.append("Only one renovated comp supports the ARV; verify with an agent or MLS pull.")
    if any((a.comp.status or "").lower() == "active" for a in adjusted):
        notes.append("Includes active listings (asking prices), weighted at half.")

    return Valuation(
        as_is_value=round(as_is, -3),
        arv=round(arv, -3),
        low=round(min(prices), -3),
        high=round(max(prices), -3),
        distressed_value=round(distressed_value, -3) if distressed_value else None,
        price_per_sqft=round(market_ppsf, 2) if market_ppsf else None,
        comps_used=sorted(adjusted, key=lambda a: -a.weight),
        comps_excluded=excluded,
        confidence=confidence,
        notes=notes,
    )
