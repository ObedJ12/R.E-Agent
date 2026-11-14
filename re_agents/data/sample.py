"""Offline demo data so the app runs before any API key is set.

Numbers are made up but realistic for a mid-priced US suburb.
"""

from __future__ import annotations

from datetime import date, timedelta

from re_agents.models import Comp, Property

_TODAY = date(2026, 11, 1)


def _comp(addr, price, beds, baths, sqft, year, dist, days, status="Inactive", corr=0.95):
    return Comp(
        address=addr,
        city="Sampleton",
        state="GA",
        zip_code="30310",
        property_type="Single Family",
        bedrooms=beds,
        bathrooms=baths,
        square_footage=sqft,
        year_built=year,
        price=price,
        status=status,
        listed_date=_TODAY - timedelta(days=days + 30),
        removed_date=_TODAY - timedelta(days=days) if status == "Inactive" else None,
        days_on_market=30,
        distance_miles=dist,
        days_old=days,
        correlation=corr,
    )


class SampleClient:
    name = "Demo data"

    def get_property(self, address: str) -> Property:
        return Property(
            address=address or "123 Demo St, Sampleton, GA 30310",
            city="Sampleton",
            state="GA",
            zip_code="30310",
            property_type="Single Family",
            bedrooms=3,
            bathrooms=2,
            square_footage=1450,
            lot_size=7400,
            year_built=1962,
            last_sale_date=date(2009, 6, 12),
            last_sale_price=98000,
        )

    def get_rent(self, subject: Property) -> float:
        return 1850.0

    def get_comps(self, subject: Property, max_radius_miles=1.0, days_old=180, comp_count=25):
        comps = [
            _comp("101 Oak Ave", 289000, 3, 2, 1500, 1965, 0.21, 34),
            _comp("88 Pine St", 275000, 3, 2, 1380, 1958, 0.35, 61),
            _comp("412 Elm Dr", 305000, 4, 2, 1620, 1970, 0.48, 22),
            _comp("19 Birch Ct", 262000, 3, 1.5, 1410, 1960, 0.30, 95),
            _comp("730 Maple Ln", 181000, 3, 2, 1460, 1961, 0.27, 40, corr=0.9),  # as-is / distressed
            _comp("55 Cedar Way", 172000, 3, 1, 1350, 1955, 0.62, 120, corr=0.88),
            _comp("240 Walnut St", 298000, 3, 2.5, 1550, 1968, 0.71, 75),
            _comp("9 Spruce Rd", 415000, 4, 3, 2400, 2004, 0.95, 50, corr=0.7),  # too big, should drop
            _comp("63 Aspen Pl", 284000, 3, 2, 1475, 1963, 0.18, 10, status="Active"),
        ]
        return 262000.0, comps
