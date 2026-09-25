"""Build the Elasticsearch-style payload used by the portal's `smart/search` endpoints.

Filter values were read from the portal's own JavaScript during Phase 0 (contractor-selection page):
  TBMT   : type in [es-notify-contractor], caseKHKQ not_in [1]         date field: publicDate
  KQLCNT : type in [es-notify-contractor], stepCode in [...step-4-kqlcnt] date field: publicDateKqlcnt
  KHLCNT : type in [es-plan-project-p]                                  date field: publicDate
Dates are sent the way the portal sends them: local (UTC+7) day bounds shifted +7h, serialised as UTC.
"""
from __future__ import annotations

from datetime import date

INDEX = "es-contractor-selection"

SOURCE_FILTERS: dict[str, dict] = {
    "tbmt": {
        "filters": [
            {"fieldName": "type", "searchType": "in", "fieldValues": ["es-notify-contractor"]},
            {"fieldName": "caseKHKQ", "searchType": "not_in", "fieldValues": ["1"]},
        ],
        "date_field": "publicDate",
    },
    "kqlcnt": {
        "filters": [
            {"fieldName": "type", "searchType": "in", "fieldValues": ["es-notify-contractor"]},
            {"fieldName": "stepCode", "searchType": "in", "fieldValues": ["notify-contractor-step-4-kqlcnt"]},
        ],
        "date_field": "publicDateKqlcnt",
    },
    "khlcnt": {
        "filters": [
            {"fieldName": "type", "searchType": "in", "fieldValues": ["es-plan-project-p"]},
        ],
        "date_field": "publicDate",
    },
}


def day_bounds(start: date, end: date) -> tuple[str, str]:
    """Portal convention: [start 00:00, end 23:59:59.059] local, +7h, as UTC ISO strings."""
    return f"{start.isoformat()}T00:00:00.000Z", f"{end.isoformat()}T23:59:59.059Z"


def build_search_payload(source: str, page: int, page_size: int,
                         start: date | None = None, end: date | None = None,
                         extra_filters: list[dict] | None = None) -> dict:
    spec = SOURCE_FILTERS[source]
    filters = [dict(f) for f in spec["filters"]] + [dict(f) for f in extra_filters or []]
    if start or end:
        lo, hi = day_bounds(start or end, end or start)
        filters.append({"fieldName": spec["date_field"], "searchType": "range",
                        "from": lo if start else None, "to": hi if end else None})
    return {
        "pageSize": page_size,
        "pageNumber": page,
        "sortBy": spec["date_field"],
        "sortType": "DESC",
        "query": [{
            "index": INDEX,
            "keyWord": "",
            "matchType": "all-1",
            "matchFields": ["notifyNo", "bidName"],
            "filters": filters,
        }],
    }
