#!/usr/bin/env bash
set -euo pipefail

OUT="/tmp/demo_acceptance_results.json"
echo "[]" > "$OUT"

SESSION=$(jq -r '.session_id' /tmp/demo_init.json)

jq -c '.[]' /tmp/demo_acceptance_questions.json | while read -r row; do
  ID=$(echo "$row" | jq -r '.id')
  Q=$(echo "$row" | jq -r '.query')

  echo "▶ Running $ID: $Q"

  REQ=$(jq -n \
    --arg session_id "$SESSION" \
    --arg coach_query "$Q" \
    '{session_id: $session_id, coach_query: $coach_query}'
  )

  RESP=$(echo "$REQ" | curl -s -X POST \
    http://127.0.0.1:8000/api/coach/query \
    -H "Content-Type: application/json" \
    -d @-)

  echo "$RESP" > /tmp/demo_last_resp.json

  jq --arg id "$ID" \
     --arg query "$Q" \
     --argjson resp "$RESP" \
     '
     . + [{
       id: $id,
       query: $query,
       intent: $resp.intent,
       answer_synthesis: $resp.answer_synthesis,
       narrative: $resp.narrative,
       confidence: ($resp.answer_synthesis.confidence // $resp.narrative.confidence),
       fact_usage: $resp.fact_usage
     }]
     ' "$OUT" > "$OUT.tmp" && mv "$OUT.tmp" "$OUT"
done

echo "✅ Demo acceptance run completed."
echo "📄 Results saved to $OUT"
