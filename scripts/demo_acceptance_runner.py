import json
from pathlib import Path
from urllib import request
import traceback


INIT_PATH = Path("/tmp/demo_init.json")
QUESTIONS_PATH = Path("/tmp/demo_acceptance_questions.json")
OUT_PATH = Path("/tmp/demo_acceptance_results.json")


def run():
    session_id = json.loads(INIT_PATH.read_text())['session_id']
    questions = json.loads(QUESTIONS_PATH.read_text())
    summary = []

    def _truncate(text: str, limit: int = 2000) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "\n...(truncated)"

    for q in questions:
        try:
            payload = json.dumps({"session_id": session_id, "coach_query": q["query"]}).encode()
            req = request.Request(
                "http://127.0.0.1:8000/api/coach/query",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with request.urlopen(req, timeout=60) as resp:
                data = resp.read().decode()
            obj = json.loads(data)
            tmp_path = Path(f"/tmp/demo_acceptance_{q['id']}.json")
            tmp_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2))

            narrative = obj.get("narrative")
            content = None
            if isinstance(narrative, dict):
                content = narrative.get("content") if narrative.get("content") is not None else narrative
            elif narrative is not None:
                content = narrative

            print(f"\n== {q['id']} :: {q['query']}")
            n_type = narrative.get("type") if isinstance(narrative, dict) else "unknown"
            n_conf = narrative.get("confidence") if isinstance(narrative, dict) else "n/a"
            print(f"type={n_type} | confidence={n_conf}")
            print("-- narrative content --")
            if isinstance(content, str):
                print(_truncate(content))
            elif content is None:
                print("(missing)")
            else:
                text = json.dumps(content, ensure_ascii=False, indent=2)
                print(_truncate(text))

            answer = obj.get("answer_synthesis") or {}
            if answer:
                print("-- answer_synthesis --")
                print(_truncate(json.dumps(answer, ensure_ascii=False, indent=2)))

            print(f"saved raw to {tmp_path}")
            summary.append({"id": q["id"], "query": q["query"], "status": "done"})
        except Exception as exc:
            print(f"\n== {q['id']} :: {q['query']}")
            print(f"ERROR: {exc}")
            traceback.print_exc()
            summary.append({"id": q["id"], "query": q["query"], "status": "error", "error": str(exc)})
            continue

    OUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"✅ summary saved to {OUT_PATH}")


if __name__ == "__main__":
    run()