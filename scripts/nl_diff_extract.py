import json
from pathlib import Path

RAW_PATH = Path('/tmp/nl_diff_acceptance_raw.json')
OUT_PATH = Path('/tmp/nl_diff_acceptance.json')

QUERIES = [
    ('Q1', '这场比赛是否属于高风险对局？'),
    ('Q2', '如果当时选择保枪而不是强起，结果可能会不同吗？'),
    ('Q3', '这场比赛里是否出现过关键的局势反转？'),
    ('Q4', '这种局势反转在整场比赛中是偶发还是反复出现？'),
]


def main():
    data = json.loads(RAW_PATH.read_text())
    summary = {
        'series_id': data.get('series_id'),
        'session_id': data.get('session_id'),
        'queries': [],
    }
    for label, q in QUERIES:
        resp = data['responses'].get(label, {})
        ctx = resp.get('context') or {}
        hp = ctx.get('hackathon_mining_plan') or {}
        facts = [f.get('fact_type') for f in (ctx.get('hackathon_evidence') or []) if f.get('fact_type')]
        nodes = (resp.get('session_analysis') or {}).get('analysis_nodes') or []
        node_types = sorted({n.get('type') for n in nodes if n.get('type')})
        msgs = resp.get('messages') or []
        answer = next((m.get('content', '') for m in msgs if m.get('role') == 'assistant'), '')
        summary['queries'].append({
            'label': label,
            'query': q,
            'mining_plan_required_facts': hp.get('required_facts'),
            'facts_used': sorted(set(facts)),
            'analysis_node_types': node_types,
            'assistant_answer': answer,
        })
    OUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print('saved', OUT_PATH)


if __name__ == '__main__':
    main()
