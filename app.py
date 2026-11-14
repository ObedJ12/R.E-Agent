"""R.E-Agent: comps and underwriting. Run with:  streamlit run app.py"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from re_agents import config
from re_agents.comps import CompRules
from re_agents.models import Condition
from re_agents.report import build_pdf
from re_agents.underwrite import DealInputs, get_data_client, underwrite

st.set_page_config(page_title="R.E-Agent", page_icon="🏠", layout="wide")
st.title("R.E-Agent: Comps and Underwriting")

has_rentcast = bool(config.RENTCAST_API_KEY)
has_claude = config.has_anthropic_credentials()

CONDITION_LABELS = {
    Condition.C1: "C1 New",
    Condition.C2: "C2 Recently renovated",
    Condition.C3: "C3 Well kept, minor wear",
    Condition.C4: "C4 Dated, some deferred maintenance",
    Condition.C5: "C5 Needs major repairs",
    Condition.C6: "C6 Severe damage",
}

with st.sidebar:
    st.subheader("Data")
    demo = st.toggle("Use demo data", value=not has_rentcast, disabled=not has_rentcast,
                     help="Add RENTCAST_API_KEY to .env to use live data.")
    st.caption(f"RentCast key: {'set' if has_rentcast else 'missing'} · Claude key: {'set' if has_claude else 'missing'}")

    st.subheader("Comp rules")
    radius = st.slider("Max distance (miles)", 0.25, 3.0, 1.0, 0.25)
    days = st.slider("Max age of comps (days)", 60, 365, 180, 15)
    sqft_pct = st.slider("Max size difference", 0.10, 0.50, 0.25, 0.05, format="%.2f")
    include_active = st.checkbox("Include active listings", value=False)

    st.subheader("Deal settings")
    buyer_pct = st.slider("End buyer % of ARV", 0.60, 0.85, 0.70, 0.01, format="%.2f")
    fee = st.number_input("Assignment fee ($)", 0, 100000, 10000, 1000)
    cost_mult = st.slider("Local cost multiplier", 0.6, 1.6, 1.0, 0.05,
                          help="0.85 for low-cost metros, 1.3 for expensive coastal markets")

address = st.text_input("Property address", placeholder="123 Main St, Atlanta, GA 30310")

col1, col2, col3 = st.columns(3)
with col1:
    condition = st.selectbox("Condition", list(CONDITION_LABELS), index=3, format_func=CONDITION_LABELS.get)
with col2:
    asking = st.number_input("Asking price ($, optional)", 0, 10_000_000, 0, 5000)
with col3:
    rent_override = st.number_input("Monthly rent ($, 0 = estimate)", 0, 50000, 0, 50)

with st.expander("Score condition from photos (Claude)", expanded=False):
    photos = st.file_uploader("Listing or walkthrough photos", type=["jpg", "jpeg", "png", "webp"],
                              accept_multiple_files=True)
    if st.button("Score photos", disabled=not (has_claude and photos)):
        from re_agents.ai import score_photos

        with st.spinner("Claude is looking at the photos..."):
            try:
                result = score_photos([(p.name, p.getvalue()) for p in photos])
                st.session_state["photo_condition"] = result
            except Exception as e:  # show any API problem to the user
                st.error(str(e))
    pc = st.session_state.get("photo_condition")
    if pc:
        st.success(f"Claude rates it C{pc.condition_score}. {pc.summary}")
        if pc.visible_issues:
            st.write("Visible issues: " + "; ".join(pc.visible_issues))
        st.caption("The condition below uses this score.")
        condition = Condition(pc.condition_score)
    if not has_claude:
        st.caption("Add ANTHROPIC_API_KEY to .env to turn this on.")

with st.expander("Correct property facts (optional)"):
    c1, c2, c3, c4 = st.columns(4)
    beds = c1.number_input("Beds", 0.0, 20.0, 0.0, 1.0)
    baths = c2.number_input("Baths", 0.0, 20.0, 0.0, 0.5)
    sqft = c3.number_input("Sqft", 0, 20000, 0, 50)
    year = c4.number_input("Year built", 0, 2030, 0, 1)

write_memo = st.checkbox("Write a deal memo with Claude", value=has_claude, disabled=not has_claude)

if st.button("Analyze deal", type="primary", disabled=not address and not demo):
    overrides = {
        "bedrooms": beds or None, "bathrooms": baths or None,
        "square_footage": sqft or None, "year_built": year or None,
    }
    inputs = DealInputs(
        address=address or "123 Demo St, Sampleton, GA 30310",
        condition=condition,
        cost_multiplier=cost_mult,
        asking_price=asking or None,
        buyer_pct_of_arv=buyer_pct,
        assignment_fee=fee,
        monthly_rent=rent_override or None,
        rules=CompRules(max_distance_miles=radius, max_days_old=days, max_sqft_diff_pct=sqft_pct,
                        include_active_listings=include_active),
    )
    with st.spinner("Pulling property data and comps..."):
        try:
            report = underwrite(inputs, get_data_client(force_demo=demo), overrides)
        except Exception as e:
            st.error(f"Could not analyze this address: {e}")
            st.stop()
    if write_memo:
        from re_agents.ai import write_deal_memo

        with st.spinner("Claude is writing the deal memo..."):
            try:
                report.memo = write_deal_memo(report.facts_for_memo())
            except Exception as e:
                st.warning(f"Memo skipped: {e}")
    st.session_state["report"] = report

report = st.session_state.get("report")
if report:
    v, s = report.valuation, report.subject
    st.subheader(s.address)
    def _n(x):
        return "?" if x is None else f"{x:,.0f}" if float(x).is_integer() else f"{x:g}"

    st.caption(f"{_n(s.bedrooms)} bd · {_n(s.bathrooms)} ba · {_n(s.square_footage)} sqft · built {s.year_built} · "
               f"last sold {s.last_sale_date} for ${s.last_sale_price or 0:,.0f} · data: {report.data_source}")
    if report.data_source == "Demo data":
        st.info("These are demo numbers, not a real property. Add a RentCast key for live data.")

    m = st.columns(5)
    m[0].metric("As-is value", f"${v.as_is_value:,.0f}")
    m[1].metric("ARV", f"${v.arv:,.0f}")
    m[2].metric("Repairs", f"${report.repairs.total:,.0f}")
    m[3].metric("Max offer (MAO)", f"${report.wholesale.mao:,.0f}")
    m[4].metric("Confidence", v.confidence)
    if report.inputs.asking_price:
        gap = report.inputs.asking_price - report.wholesale.mao
        st.write(f"Asking is **${gap:,.0f} {'above' if gap > 0 else 'below'}** your max offer.")
    for note in v.notes:
        st.caption(note)

    if report.memo:
        st.markdown("#### Deal memo")
        st.markdown(report.memo)

    st.markdown("#### Comps used")
    st.dataframe(pd.DataFrame([{
        "Address": a.comp.address, "Price": a.comp.price, "Adjusted": a.adjusted_price,
        "Adjustments": ", ".join(f"{k} {val:+,.0f}" for k, val in a.adjustments.items()) or "-",
        "Bd": a.comp.bedrooms, "Ba": a.comp.bathrooms, "Sqft": a.comp.square_footage,
        "Built": a.comp.year_built, "Miles": a.comp.distance_miles, "Days old": a.comp.days_old,
        "Status": a.comp.status, "Weight": a.weight,
    } for a in v.comps_used]), hide_index=True, width="stretch")
    if v.comps_excluded:
        with st.expander(f"{len(v.comps_excluded)} comps excluded"):
            st.dataframe(pd.DataFrame([{
                "Address": a.comp.address, "Price": a.comp.price, "Reason": a.excluded_reason,
            } for a in v.comps_excluded]), hide_index=True, width="stretch")

    st.markdown("#### Exit strategies")
    t1, t2, t3, t4 = st.tabs(["Wholesale", "Fix and flip", "Rental", "BRRRR"])
    with t1:
        st.write(f"Offer up to **${report.wholesale.mao:,.0f}**. Your end buyer pays "
                 f"${report.wholesale.buyer_price:,.0f} ({report.inputs.buyer_pct_of_arv:.0%} of ARV minus repairs), "
                 f"leaving your ${report.wholesale.assignment_fee:,.0f} fee.")
    with t2:
        st.json(report.flip.model_dump())
    with t3:
        st.json(report.rental.model_dump())
    with t4:
        st.json(report.brrrr.model_dump())

    st.markdown("#### Repair estimate")
    st.dataframe(pd.DataFrame([l.model_dump() for l in report.repairs.lines]), hide_index=True,
                 width="stretch")
    st.caption(f"Scope: {report.repairs.scope}; subtotal ${report.repairs.subtotal:,.0f} plus "
               f"{report.repairs.contingency_pct:.0%} contingency = ${report.repairs.total:,.0f}")

    st.download_button("Download PDF report", build_pdf(report), file_name="deal-report.pdf",
                       mime="application/pdf")
