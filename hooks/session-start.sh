#!/usr/bin/env bash
# SessionStart hook for co-researcher plugin

set -euo pipefail

task_context=""
if [ -n "${CLAUDE_CODE_TASK_LIST_ID:-}" ]; then
    task_context="\nYou are resuming work on Task List: ${CLAUDE_CODE_TASK_LIST_ID}. Use the 'Task' tools to check the status of your research."
fi

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Co-Researcher is active. Core principles:\n1. **Systemic Honesty**: Never fabricate citations, data, or results. If you don't know, state it. Accuracy > Count.\n2. **Skill-First**: Before answering a research question, check the co-researcher skills and follow the matched skill's protocol exactly.\n3. **Methodological Rigor**: Adhere to the standards each skill defines (e.g., PRISMA for reviews, APA for citations).${task_context}"
  }
}
EOF

exit 0
