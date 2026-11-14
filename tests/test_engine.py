from re_agents import calculators as calc
from re_agents.comps import CompRules, value_property
from re_agents.data.cache import ResponseCache
from re_agents.data.rentcast import parse_comp
from re_agents.data.sample import SampleClient
from re_agents.models import Condition
from re_agents.repairs import estimate_repairs
from re_agents.report import build_pdf
from re_agents.underwrite import DealInputs, underwrite


def _sample():
    dc = SampleClient()
    subject = dc.get_property("123 Demo St")
    _, comps = dc.get_comps(subject)
    return subject, comps


def test_filters_drop_bad_comps():
    subject, comps = _sample()
    v = value_property(subject, comps)
    reasons = {a.comp.address: a.excluded_reason for a in v.comps_excluded}
    assert "9 Spruce Rd" in reasons  # 2,400 sqft vs 1,450
    assert reasons["63 Aspen Pl"] == "still an active listing"
    assert all(a.comp.address not in reasons for a in v.comps_used)


def test_arv_above_as_is_and_within_range():
    subject, comps = _sample()
    v = value_property(subject, comps, repairs_total=60_000)
    assert v.low <= v.arv <= v.high  # low/high = renovated comp range
    assert v.as_is_value < v.arv
    assert 250_000 <= v.arv <= 320_000


def test_distressed_comps_split_from_renovated():
    subject, comps = _sample()
    v = value_property(subject, comps)
    assert v.distressed_value is not None and v.distressed_value < 200_000
    # The two cheap sales must not drag the ARV down.
    assert v.arv > 270_000


def test_good_condition_as_is_equals_arv():
    report = underwrite(DealInputs(address="x", condition=Condition.C2), SampleClient())
    assert report.valuation.as_is_value == report.valuation.arv


def test_adjustment_direction():
    subject, comps = _sample()
    v = value_property(subject, comps)
    elm = next(a for a in v.comps_used if a.comp.address == "412 Elm Dr")  # 4 bd, bigger
    assert elm.adjustments["beds"] < 0 and elm.adjustments["sqft"] < 0
    assert elm.adjusted_price < elm.comp.price


def test_no_comps_raises():
    subject, comps = _sample()
    try:
        value_property(subject, comps, CompRules(max_distance_miles=0.01))
    except ValueError as e:
        assert "No usable comps" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_repairs_scale_with_condition():
    subject, _ = _sample()
    light = estimate_repairs(subject, Condition.C3).total
    heavy = estimate_repairs(subject, Condition.C5).total
    assert 0 < light < heavy
    assert estimate_repairs(subject, Condition.C5, cost_multiplier=1.3).total > heavy


def test_wholesale_70_rule():
    r = calc.wholesale(arv=300_000, repairs=40_000, buyer_pct_of_arv=0.70, assignment_fee=10_000)
    assert r.buyer_price == 170_000
    assert r.mao == 160_000
    assert r.spread_ok


def test_flip_and_rental_math():
    f = calc.flip(arv=300_000, purchase=160_000, repairs=40_000)
    assert f.net_profit > 0 and f.cash_needed > 0
    r = calc.rental(price=200_000, monthly_rent=1_850)
    assert r.monthly_debt > 900  # 150k at 7% over 30 years is about $998
    b = calc.brrrr(arv=300_000, purchase=160_000, repairs=40_000, monthly_rent=2_100)
    assert b.refi_loan == 225_000 and b.cash_left_in < 0  # all cash out


def test_full_underwrite_and_pdf():
    report = underwrite(DealInputs(address="123 Demo St", condition=Condition.C4), SampleClient())
    assert report.wholesale.mao < report.valuation.arv
    assert "ARV" in report.facts_for_memo()
    pdf = build_pdf(report)
    assert pdf[:4] == b"%PDF" and len(pdf) > 2000


def test_parse_rentcast_comp():
    raw = {
        "formattedAddress": "1 Test St, Austin, TX 78701", "city": "Austin", "state": "TX",
        "zipCode": "78701", "propertyType": "Single Family", "bedrooms": 3, "bathrooms": 2,
        "squareFootage": 1500, "yearBuilt": 1990, "status": "Inactive", "price": 350000,
        "listedDate": "2026-06-01T00:00:00.000Z", "removedDate": "2026-07-15T00:00:00.000Z",
        "daysOnMarket": 44, "distance": 0.4, "daysOld": 120, "correlation": 0.97,
    }
    c = parse_comp(raw)
    assert c.price == 350000 and c.removed_date.isoformat() == "2026-07-15"
    assert c.distance_miles == 0.4


def test_cache_roundtrip(tmp_path):
    cache = ResponseCache(tmp_path / "c.sqlite")
    key = ResponseCache.make_key("/x", {"b": 2, "a": 1})
    assert key == ResponseCache.make_key("/x", {"a": 1, "b": 2})
    assert cache.get(key) is None
    cache.set(key, {"ok": True})
    assert cache.get(key) == {"ok": True}
