#!/usr/bin/env bash
# Co-researcher one-time environment setup.
# Ensures `uv` is installed and warms the literature-review script cache.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

say() { printf '\033[1;36m[co-researcher]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[co-researcher]\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31m[co-researcher]\033[0m %s\n' "$*" >&2; exit 1; }

ensure_uv() {
    if command -v uv >/dev/null 2>&1; then
        say "uv detected: $(uv --version)"
        return 0
    fi

    if [ -x "${HOME}/.local/bin/uv" ]; then
        say "uv found at ~/.local/bin — adding to PATH for this session."
        export PATH="${HOME}/.local/bin:${PATH}"
        say "uv version: $(uv --version)"
        warn "Add 'export PATH=\"\$HOME/.local/bin:\$PATH\"' to your shell profile to make this permanent."
        return 0
    fi

    if command -v brew >/dev/null 2>&1 && brew --prefix uv >/dev/null 2>&1; then
        say "uv is installed via Homebrew but not linked. Linking now."
        brew link --overwrite uv
        say "uv version: $(uv --version)"
        return 0
    fi

    say "uv not found. Installing from https://astral.sh — required for literature-review scripts."
    if ! command -v curl >/dev/null 2>&1; then
        fail "curl is required to install uv. Install curl or uv manually, then re-run."
    fi
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${PATH}"
    command -v uv >/dev/null 2>&1 || fail "uv install completed but binary not on PATH. Open a new shell and re-run setup."
    say "uv installed: $(uv --version)"
    warn "Add 'export PATH=\"\$HOME/.local/bin:\$PATH\"' to your shell profile."
}

prompt_openalex_key() {
    local env_file="${HOME}/.env"

    if [ -f "${env_file}" ] && grep -q '^OPENALEX_API_KEY=' "${env_file}" 2>/dev/null; then
        say "OPENALEX_API_KEY already set in ~/.env — skipping."
        return 0
    fi

    say "OpenAlex API key (optional but recommended)."
    say "  - Without a key: \$0.01/day budget — ~10 filter queries or 1 search/day."
    say "  - With a free key: \$1/day budget, ~10 req/s. Get one at https://openalex.org → account settings."
    printf '\033[1;36m[co-researcher]\033[0m Paste OpenAlex API key (input hidden, press Enter to skip): '
    local key=""
    read -s key || true
    echo

    if [ -z "${key}" ]; then
        warn "No key provided. OpenAlex will run in the unauthenticated polite pool."
        return 0
    fi

    touch "${env_file}"
    chmod 600 "${env_file}"
    printf 'OPENALEX_API_KEY=%s\n' "${key}" >> "${env_file}"
    unset key
    say "Saved to ~/.env (mode 600). Never read or print this file."
}

warm_cache() {
    local lit_dir="${PLUGIN_ROOT}/skills/literature-review"
    if [ ! -d "${lit_dir}/scripts" ]; then
        warn "literature-review/scripts not found — skipping cache warmup."
        return 0
    fi
    say "Warming dependency cache for literature-review scripts (one-time)."
    (
        cd "${lit_dir}"
        for script in scripts/openalex_cli.py scripts/europepmc_api.py scripts/search_arxiv.py; do
            [ -f "${script}" ] || continue
            uv run "${script}" --help >/dev/null 2>&1 || warn "Cache warmup failed for ${script} (non-fatal)."
        done
    )
    say "Cache warmed."
}

main() {
    say "Setting up co-researcher environment at ${PLUGIN_ROOT}"
    ensure_uv
    prompt_openalex_key
    warm_cache
    say "Setup complete. Literature-review scripts are ready."
}

main "$@"
