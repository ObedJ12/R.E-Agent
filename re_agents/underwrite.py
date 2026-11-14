"""Comps and Underwriting agent: address in, full deal report out."""

from __future__ import annotations

from pydantic import BaseModel

from re_agents import calculators as calc
from re_agents import config
from re_agents.comps import CompRules, value_property
from re_agents.models import Condition, Property, RepairEstimate, Valuation
from re_agents.repairs import estimate_repairs


class DealInputs(BaseModel):
    address: str
    condition: Condition = Condition.C4
    cost_multiplier: float = 1.0
    asking_price: float | None = None
    buyer_pct_of_arv: float = 0.70
    assignment_fee: float = 10000
    monthly_rent: float | None = None  # None = use the rent estimate
    rules: CompRules = CompRules()


class DealReport(BaseModel):
    inputs: DealInputs
    data_source: str
    subject: Property
    vendor_avm: float | None
    rent_estimate: float | None
    valuation: Valuation
    repairs: RepairEstimate
    wholesale: calc.WholesaleResult
    flip: calc.FlipResult
    rental: calc.RentalResult
    brrrr: calc.BRRRRResult
    memo: str | None = None

    def facts_for_memo(self) -> str:
        v, s = self.valuation, self.subject
        lines = [
            f"Subject: {s.address}; {s.bedrooms} bd / {s.bathrooms} ba, {s.square_footage} sqft, built {s.year_built}.",
            f"Last sale: {s.last_sale_date} for {s.last_sale_price}.",
            f"Asking price: {self.inputs.asking_price or 'unknown'}.",
            f"Condition: C{self.repairs.condition.value} ({self.repairs.scope}); repair estimate ${self.repairs.total:,.0f}.",
            f"As-is value ${v.as_is_value:,.0f}; ARV ${v.arv:,.0f}; range ${v.low:,.0f}-${v.high:,.0f};"
            f" {len(v.comps_used)} comps used, confidence {v.confidence}. Notes: {'; '.join(v.notes) or 'none'}.",
            f"Data source vendor AVM: {self.vendor_avm}. Comps are listing data, not MLS closed sales.",
            f"Wholesale: MAO ${self.wholesale.mao:,.0f} with ${self.wholesale.assignment_fee:,.0f} fee "
            f"(end buyer at ${self.wholesale.buyer_price:,.0f}).",
            f"Flip at MAO: net profit ${self.flip.net_profit:,.0f}, ROI on cash {self.flip.roi_on_cash:.0%},"
            f" cash needed ${self.flip.cash_needed:,.0f}.",
            f"Rental bought at as-is value plus repairs: rent ${self.rental.monthly_rent:,.0f}/mo, cash flow ${self.rental.monthly_cash_flow:,.0f}/mo,"
            f" cap rate {self.rental.cap_rate:.1%}.",
            f"BRRRR from MAO: cash left in ${self.brrrr.cash_left_in:,.0f}, cash flow ${self.brrrr.monthly_cash_flow:,.0f}/mo.",
        ]
        return "\n".join(lines)


def get_data_client(force_demo: bool = False):
    if not force_demo and config.RENTCAST_API_KEY:
        from re_agents.data.rentcast import RentCastClient

        return RentCastClient()
    from re_agents.data.sample import SampleClient

    return SampleClient()


def underwrite(inputs: DealInputs, data_client=None, subject_override: dict | None = None) -> DealReport:
    dc = data_client or get_data_client()
    subject = dc.get_property(inputs.address)
    if subject is None:
        subject = Property(address=inputs.address)
    if subject_override:
        subject = subject.model_copy(update={k: v for k, v in subject_override.items() if v is not None})

    avm, comps = dc.get_comps(
        subject,
        max_radius_miles=inputs.rules.max_distance_miles,
        days_old=inputs.rules.max_days_old,
    )
    repairs = estimate_repairs(subject, inputs.condition, inputs.cost_multiplier)
    needs_work = inputs.condition.value >= Condition.C4.value
    valuation = value_property(subject, comps, inputs.rules, repairs.total if needs_work else 0.0, needs_work)
    rent = inputs.monthly_rent or dc.get_rent(subject) or 0.0

    ws = calc.wholesale(valuation.arv, repairs.total, inputs.buyer_pct_of_arv, inputs.assignment_fee)
    purchase = max(ws.mao, 0)
    return DealReport(
        inputs=inputs,
        data_source=dc.name,
        subject=subject,
        vendor_avm=avm,
        rent_estimate=rent or None,
        valuation=valuation,
        repairs=repairs,
        wholesale=ws,
        flip=calc.flip(valuation.arv, purchase, repairs.total),
        rental=calc.rental(valuation.as_is_value, rent, repairs=repairs.total if needs_work else 0.0),
        brrrr=calc.brrrr(valuation.arv, purchase, repairs.total, rent),
    )
