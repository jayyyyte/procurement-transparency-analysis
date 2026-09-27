from datetime import date

from src.crawler.es_query import build_search_payload


def test_tbmt_payload_without_dates():
    p = build_search_payload("tbmt", page=3, page_size=10)
    assert p["pageNumber"] == 3 and p["pageSize"] == 10
    f = p["query"][0]["filters"]
    assert {"fieldName": "type", "searchType": "in", "fieldValues": ["es-notify-contractor"]} in f
    assert not any(x["fieldName"] == "publicDate" for x in f)


def test_kqlcnt_uses_result_date_field():
    p = build_search_payload("kqlcnt", 0, 10, start=date(2025, 1, 2), end=date(2025, 1, 2))
    rng = [x for x in p["query"][0]["filters"] if x["searchType"] == "range"][0]
    assert rng["fieldName"] == "publicDateKqlcnt"
    assert rng["from"] == "2025-01-02T00:00:00.000Z" and rng["to"] == "2025-01-02T23:59:59.059Z"
    assert p["sortBy"] == "publicDateKqlcnt"
