import json
import requests


def main():
    series_id = "2819676"
    init_resp = requests.post(
        "http://127.0.0.1:8000/api/coach/init",
        headers={"Content-Type": "application/json"},
        json={"grid_series_id": series_id},
        timeout=120,
    )
    init_body = init_resp.json()
    print("=== INIT status", init_resp.status_code)
    print(json.dumps(init_body, ensure_ascii=False, indent=2))

    session_id = init_body.get("session_id")
    if not session_id:
        raise SystemExit("init failed: missing session_id")

    queries = [
        ("Q1", "这场比赛是否属于高风险对局？"),
        ("Q2", "如果当时选择保枪而不是强起，结果可能会不同吗？"),
        ("Q3", "这场比赛里是否出现过关键的局势反转？"),
        ("Q4", "这种局势反转在整场比赛中是偶发还是反复出现？"),
    ]
    url = "http://127.0.0.1:8000/api/coach/query"
    headers = {"Content-Type": "application/json"}

    all_responses = {}
    for label, q in queries:
        body = {"coach_query": q, "series_id": series_id, "session_id": session_id}
        resp = requests.post(url, headers=headers, json=body, timeout=300)
        all_responses[label] = resp.json()
        hp = resp.json().get("hackathon_mining_plan", {})
        print(f"=== {label} status {resp.status_code}")
        print(
            json.dumps(
                {
                    "intent": hp.get("intent"),
                    "required_facts": hp.get("required_facts"),
                    "scope": hp.get("scope"),
                    "constraints": hp.get("constraints"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print()

    with open("/tmp/hackathon_nl_results.json", "w") as f:
        json.dump(
            {"session_id": session_id, "series_id": series_id, "responses": all_responses},
            f,
            ensure_ascii=False,
            indent=2,
        )
    print("session", session_id)
    print("saved to /tmp/hackathon_nl_results.json")


if __name__ == "__main__":
    main()
