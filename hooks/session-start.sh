#!/usr/bin/env bash
# SessionStart hook for co-researcher plugin

set -euo pipefail

# Determine plugin root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Read using-co-researcher content
using_co_researcher_content=$(cat "${PLUGIN_ROOT}/skills/using-co-researcher/SKILL.md" 2>&1 || echo "Error reading using-co-researcher skill")

# Escape outputs for JSON using pure bash
escape_for_json() {
    local input="$1"
    local output=""
    local i char
    for (( i=0; i<${#input}; i++ )); do
        char="${input:$i:1}"
        case "$char" in
            $'\\') output+='\\' ;;
            '"') output+='\"' ;;
            $'\n') output+='\n' ;;
            $'\r') output+='\r' ;;
            $'\t') output+='\t' ;;
            *) output+="$char" ;;
        esac
    done
    printf '%s' "$output"
}

using_co_researcher_escaped=$(escape_for_json "$using_co_researcher_content")

# Check for Task List
task_context=""
if [ -n "${CLAUDE_CODE_TASK_LIST_ID:-}" ]; then
    task_context="You are resuming work on Task List: ${CLAUDE_CODE_TASK_LIST_ID}. Use the 'Task' tools to check the status of your research."
fi
task_context_escaped=$(escape_for_json "$task_context")

# Output context injection as JSON
cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "<EXTREMELY_IMPORTANT>\nYou have Co-Researcher Powers.\n\n**Below is the full content of your 'using-co-researcher' skill - your introduction to the system. For all other skills, use your available tools:**\n\n${using_co_researcher_escaped}\n\n${task_context_escaped}\n</EXTREMELY_IMPORTANT>"
  }
}
EOF

exit 0
