"""RentCast property data client (https://developers.rentcast.io).

Uses two endpoints:
  GET /properties   public-record facts for the subject (beds, baths, sqft, last sale)
  GET /avm/value    value estimate plus nearby comparable listings

RentCast comparables are listings, not recorded closings: "Inactive" means the
listing came off the market (usually sold), and `price` is the last list price.
Treat values as a first pass until MLS sold data is connected.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx

from re_agents import config
from re_agents.data.cache import ResponseCache
from re_agents.models import Comp, Property

BASE_URL = "https://api.rentcast.io/v1"


class RentCastError(RuntimeError):
    pass


def _to_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _property_fields(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "address": raw.get("formattedAddress") or raw.get("addressLine1") or "",
        "city": raw.get("city"),
        "state": raw.get("state"),
        "zip_code": raw.get("zipCode"),
        "latitude": raw.get("latitude"),
        "longitude": raw.get("longitude"),
        "property_type": raw.get("propertyType"),
        "bedrooms": raw.get("bedrooms"),
        "bathrooms": raw.get("bathrooms"),
        "square_footage": raw.get("squareFootage"),
        "lot_size": raw.get("lotSize"),
        "year_built": raw.get("yearBuilt"),
        "last_sale_date": _to_date(raw.get("lastSaleDate")),
        "last_sale_price": raw.get("lastSalePrice"),
    }


def parse_property(raw: dict[str, Any]) -> Property:
    return Property(**_property_fields(raw))


def parse_comp(raw: dict[str, Any]) -> Comp:
    return Comp(
        **_property_fields(raw),
        price=raw["price"],
        status=raw.get("status"),
        listed_date=_to_date(raw.get("listedDate")),
        removed_date=_to_date(raw.get("removedDate")),
        days_on_market=raw.get("daysOnMarket"),
        distance_miles=raw.get("distance"),
        days_old=raw.get("daysOld"),
        correlation=raw.get("correlation"),
    )


class RentCastClient:
    name = "RentCast"

    def __init__(self, api_key: str | None = None, cache: ResponseCache | None = None) -> None:
        self.api_key = api_key or config.RENTCAST_API_KEY
        if not self.api_key:
            raise RentCastError("RENTCAST_API_KEY is not set. Add it to your .env file.")
        self.cache = cache or ResponseCache(config.CACHE_DIR / "rentcast.sqlite", config.CACHE_TTL_DAYS)
        self.http = httpx.Client(
            base_url=BASE_URL,
            headers={"X-Api-Key": self.api_key, "Accept": "application/json"},
            timeout=30,
        )

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        params = {k: v for k, v in params.items() if v is not None}
        key = ResponseCache.make_key(path, params)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        resp = self.http.get(path, params=params)
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise RentCastError(f"RentCast {path} failed ({resp.status_code}): {resp.text[:300]}")
        body = resp.json()
        self.cache.set(key, body)
        return body

    def get_property(self, address: str) -> Property | None:
        body = self._get("/properties", {"address": address, "limit": 1})
        if not body:
            return None
        records = body if isinstance(body, list) else [body]
        return parse_property(records[0]) if records else None

    def get_rent(self, subject: Property) -> float | None:
        body = self._get(
            "/avm/rent/long-term",
            {
                "address": subject.address,
                "propertyType": subject.property_type,
                "bedrooms": subject.bedrooms,
                "bathrooms": subject.bathrooms,
                "squareFootage": subject.square_footage,
            },
        )
        return (body or {}).get("rent")

    def get_comps(
        self,
        subject: Property,
        max_radius_miles: float = 1.0,
        days_old: int = 180,
        comp_count: int = 25,
    ) -> tuple[float | None, list[Comp]]:
        """Returns (vendor AVM estimate, comparables)."""
        body = self._get(
            "/avm/value",
            {
                "address": subject.address,
                "propertyType": subject.property_type,
                "bedrooms": subject.bedrooms,
                "bathrooms": subject.bathrooms,
                "squareFootage": subject.square_footage,
                "maxRadius": max_radius_miles,
                "daysOld": days_old,
                "compCount": comp_count,
            },
        )
        if not body:
            return None, []
        comps = [parse_comp(c) for c in body.get("comparables", []) if c.get("price")]
        return body.get("price"), comps
