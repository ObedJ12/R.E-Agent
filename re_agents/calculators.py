"""Deal math for each exit strategy. All inputs are plain numbers so the
Streamlit sliders and tests can drive them directly."""

from __future__ import annotations

from pydantic import BaseModel


class WholesaleResult(BaseModel):
    mao: float  # max you offer the seller
    buyer_price: float  # what your end buyer pays you (their MAO)
    assignment_fee: float
    spread_ok: bool


def wholesale(
    arv: float,
    repairs: float,
    buyer_pct_of_arv: float = 0.70,
    assignment_fee: float = 10000,
) -> WholesaleResult:
    """Classic 70% rule: end buyer pays ARV x pct - repairs; you subtract your fee."""
    buyer_price = arv * buyer_pct_of_arv - repairs
    mao = buyer_price - assignment_fee
    return WholesaleResult(
        mao=round(mao, -2),
        buyer_price=round(buyer_price, -2),
        assignment_fee=assignment_fee,
        spread_ok=mao > 0,
    )


class FlipResult(BaseModel):
    total_cost: float
    cash_needed: float
    holding_costs: float
    selling_costs: float
    financing_costs: float
    net_profit: float
    roi_on_cash: float
    margin_on_arv: float


def flip(
    arv: float,
    purchase: float,
    repairs: float,
    months: int = 6,
    monthly_holding: float = 600,  # taxes, insurance, utilities
    buy_closing_pct: float = 0.02,
    sell_closing_pct: float = 0.08,  # agent commissions + closing
    loan_ltc: float = 0.85,  # hard money: % of purchase + repairs financed
    loan_rate: float = 0.12,
    loan_points: float = 0.02,
) -> FlipResult:
    loan = (purchase + repairs) * loan_ltc
    financing = loan * loan_points + loan * loan_rate / 12 * months
    holding = monthly_holding * months
    buy_closing = purchase * buy_closing_pct
    selling = arv * sell_closing_pct
    total = purchase + repairs + holding + buy_closing + selling + financing
    profit = arv - total
    cash = purchase + repairs - loan + buy_closing + holding + loan * loan_points
    return FlipResult(
        total_cost=round(total),
        cash_needed=round(cash),
        holding_costs=round(holding),
        selling_costs=round(selling),
        financing_costs=round(financing),
        net_profit=round(profit),
        roi_on_cash=round(profit / cash, 4) if cash > 0 else 0.0,
        margin_on_arv=round(profit / arv, 4) if arv else 0.0,
    )


def _mortgage_payment(principal: float, annual_rate: float, years: int = 30) -> float:
    r = annual_rate / 12
    n = years * 12
    if r == 0:
        return principal / n
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


class RentalResult(BaseModel):
    monthly_rent: float
    monthly_expenses: float
    monthly_debt: float
    monthly_cash_flow: float
    noi_annual: float
    cap_rate: float
    cash_invested: float
    cash_on_cash: float


def rental(
    price: float,
    monthly_rent: float,
    repairs: float = 0,
    down_pct: float = 0.25,
    rate: float = 0.07,
    tax_insurance_monthly: float = 350,
    vacancy_pct: float = 0.08,
    maintenance_pct: float = 0.08,
    management_pct: float = 0.10,
    closing_pct: float = 0.03,
) -> RentalResult:
    loan = price * (1 - down_pct)
    debt = _mortgage_payment(loan, rate)
    opex = tax_insurance_monthly + monthly_rent * (vacancy_pct + maintenance_pct + management_pct)
    noi = (monthly_rent - opex) * 12
    cash_in = price * down_pct + price * closing_pct + repairs
    flow = monthly_rent - opex - debt
    basis = price + repairs
    return RentalResult(
        monthly_rent=monthly_rent,
        monthly_expenses=round(opex),
        monthly_debt=round(debt),
        monthly_cash_flow=round(flow),
        noi_annual=round(noi),
        cap_rate=round(noi / basis, 4) if basis else 0.0,
        cash_invested=round(cash_in),
        cash_on_cash=round(flow * 12 / cash_in, 4) if cash_in else 0.0,
    )


class BRRRRResult(BaseModel):
    all_in: float
    refi_loan: float
    cash_left_in: float
    monthly_cash_flow: float
    cash_on_cash: float | None  # None means infinite (all cash pulled out)


def brrrr(
    arv: float,
    purchase: float,
    repairs: float,
    monthly_rent: float,
    holding_and_closing: float = 8000,
    refi_ltv: float = 0.75,
    refi_rate: float = 0.075,
    tax_insurance_monthly: float = 350,
    vacancy_pct: float = 0.08,
    maintenance_pct: float = 0.08,
    management_pct: float = 0.10,
) -> BRRRRResult:
    all_in = purchase + repairs + holding_and_closing
    loan = arv * refi_ltv
    left_in = all_in - loan
    debt = _mortgage_payment(loan, refi_rate)
    opex = tax_insurance_monthly + monthly_rent * (vacancy_pct + maintenance_pct + management_pct)
    flow = monthly_rent - opex - debt
    return BRRRRResult(
        all_in=round(all_in),
        refi_loan=round(loan),
        cash_left_in=round(left_in),
        monthly_cash_flow=round(flow),
        cash_on_cash=round(flow * 12 / left_in, 4) if left_in > 0 else None,
    )
