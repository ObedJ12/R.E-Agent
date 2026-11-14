"""Rule-based rehab estimate from condition score and house size.

Costs are national mid-range defaults (2026 dollars). Set `cost_multiplier`
for your market (e.g. 0.85 in low-cost metros, 1.3 on the coasts) or override
line items in the app.
"""

from __future__ import annotations

from re_agents.models import Condition, Property, RepairEstimate, RepairLine

SCOPE_BY_CONDITION = {
    Condition.C1: "none",
    Condition.C2: "cosmetic",
    Condition.C3: "cosmetic",
    Condition.C4: "moderate",
    Condition.C5: "full gut",
    Condition.C6: "full gut",
}


def estimate_repairs(
    subject: Property,
    condition: Condition,
    cost_multiplier: float = 1.0,
    roof_needed: bool | None = None,
    hvac_needed: bool | None = None,
) -> RepairEstimate:
    sqft = subject.square_footage or 1400
    baths = max(1, int(round(subject.bathrooms or 1)))
    age = 2026 - (subject.year_built or 1980)
    scope = SCOPE_BY_CONDITION[condition]
    m = cost_multiplier
    lines: list[RepairLine] = []

    def add(item: str, cost: float, note: str = "") -> None:
        lines.append(RepairLine(item=item, cost=round(cost * m, -1), note=note))

    if scope == "none":
        add("Make-ready (clean, touch-up)", 1500)
    if scope in ("cosmetic", "moderate", "full gut"):
        add("Interior paint", 2.75 * sqft, "$2.75/sqft")
        add("Flooring (LVP)", 4.5 * sqft * (0.6 if scope == "cosmetic" else 0.9), "$4.50/sqft installed")
        add("Fixtures, hardware, lighting", 2500)
        add("Landscaping and exterior touch-up", 2000)
    if scope in ("moderate", "full gut"):
        add("Kitchen", 18000 if scope == "moderate" else 28000)
        add("Bathrooms", baths * (8000 if scope == "moderate" else 12000), f"{baths} bath(s)")
        add("Exterior paint or siding repair", 5000)
        add("Windows and doors (partial)", 4000)
    if scope == "full gut":
        add("Electrical update", 6.0 * sqft, "$6/sqft")
        add("Plumbing update", 4.0 * sqft, "$4/sqft")
        add("Drywall and framing repair", 5.0 * sqft, "$5/sqft")
        add("Permits and dumpsters", 4500)

    if roof_needed or (roof_needed is None and age > 25 and scope != "cosmetic" and scope != "none"):
        add("Roof replacement", 6.5 * sqft * 1.15, "assumed: roof over 25 years old")
    if hvac_needed or (hvac_needed is None and scope == "full gut"):
        add("HVAC system", 9000, "assumed for full rehab")

    contingency = {"none": 0.05, "cosmetic": 0.10, "moderate": 0.12, "full gut": 0.15}[scope]
    return RepairEstimate(condition=condition, scope=scope, lines=lines, contingency_pct=contingency)
