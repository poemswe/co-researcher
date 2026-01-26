#!/usr/bin/env bash
# SessionStart hook for co-researcher plugin

set -euo pipefail

# Determine plugin root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Read using-co-researcher content
using_coresearcher_content=$(cat "${PLUGIN_ROOT}/skills/using-co-researcher/SKILL.md" 2>&1 || echo "Error reading using-co-researcher skill")

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

using_coresearcher_escaped=$(escape_for_json "$using_coresearcher_content")

# Output context injection as JSON
cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "<EXTREMELY_IMPORTANT>\nYou have Co-Researcher Powers.\n\n**Below is the full content of your 'using-co-researcher' skill - your introduction to the system. For all other skills, use your available tools:**\n\n${using_coresearcher_escaped}\n</EXTREMELY_IMPORTANT>"
  }
}
EOF

exit 0
