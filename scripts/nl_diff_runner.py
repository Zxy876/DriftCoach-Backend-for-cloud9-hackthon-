import json
import requests

SERIES_ID = "2819676"
QUERIES = [
    ("Q1", "这场比赛是否属于高风险对局？"),
    ("Q2", "如果当时选择保枪而不是强起，结果可能会不同吗？"),
    ("Q3", "这场比赛里是否出现过关键的局势反转？"),
    ("Q4", "这种局势反转在整场比赛中是偶发还是反复出现？"),
]


def main():
    init_resp = requests.post(
        "http://127.0.0.1:8000/api/coach/init",
        headers={"Content-Type": "application/json"},
        json={"grid_series_id": SERIES_ID},
        timeout=120,
    )
    init_resp.raise_for_status()
    init_body = init_resp.json()
    session_id = init_body.get("session_id")
    print("INIT", init_resp.status_code, init_body)

    url = "http://127.0.0.1:8000/api/coach/query"
    headers = {"Content-Type": "application/json"}
    all_responses = {}
    for label, q in QUERIES:
        resp = requests.post(
            url,
            headers=headers,
            json={"coach_query": q, "series_id": SERIES_ID, "session_id": session_id},
            timeout=300,
        )
        print(label, resp.status_code)
        all_responses[label] = resp.json()

    with open("/tmp/nl_diff_acceptance_raw.json", "w") as f:
        json.dump({"series_id": SERIES_ID, "session_id": session_id, "responses": all_responses}, f, ensure_ascii=False, indent=2)
    print("saved /tmp/nl_diff_acceptance_raw.json")


if __name__ == "__main__":
    main()
