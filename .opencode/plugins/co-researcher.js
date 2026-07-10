/**
 * Co-Researcher plugin for OpenCode.ai
 *
 * Injects co-researcher bootstrap context via system prompt transform.
 * Skills are discovered via OpenCode's native skill tool from symlinked directory.
 */

import path from 'path';
import os from 'os';

// Normalize a path: trim whitespace, expand ~, resolve to absolute
const normalizePath = (p, homeDir) => {
    if (!p || typeof p !== 'string') return null;
    let normalized = p.trim();
    if (!normalized) return null;
    if (normalized.startsWith('~/')) {
        normalized = path.join(homeDir, normalized.slice(2));
    } else if (normalized === '~') {
        normalized = homeDir;
    }
    return path.resolve(normalized);
};

export const CoResearcherPlugin = async ({ client, directory }) => {
    const homeDir = os.homedir();
    const envConfigDir = normalizePath(process.env.OPENCODE_CONFIG_DIR, homeDir);
    const configDir = envConfigDir || path.join(homeDir, '.config/opencode');

    // Helper to generate bootstrap content
    const getBootstrapContent = () => {
        // We can inject specific instructions or load a "using-co-researcher" skill if it existed.
        // For now, we'll inject the core bootstrap message directly.

        const toolMapping = `**Tool Mapping for OpenCode:**
When skills reference tools you don't have, substitute OpenCode equivalents:
- \`TodoWrite\` → \`update_plan\`
- \`Task\` tool with subagents → Use OpenCode's subagent system (@mention)
- \`Skill\` tool → OpenCode's native \`skill\` tool
- \`Read\`, \`Write\`, \`Edit\`, \`Bash\` → Your native tools
`;

        // Try to read a bootstrap file if one existed, but here we construct it.
        // We'll point to the Co-Researcher skills.

        return `<EXTREMELY_IMPORTANT>
You have **Co-Researcher Powers**. You are an expert academic research assistant with PhD-level capabilities.

**Core principles:**
1. **Systemic Honesty**: Never fabricate citations, data, or results. If you don't know, state it. Accuracy > Count.
2. **Skill-First**: Before answering a research question, check the co-researcher skills and follow the matched skill's protocol exactly.
3. **Methodological Rigor**: Adhere to the standards each skill defines (e.g., PRISMA for reviews, APA for citations).

**Skills location:**
Co-Researcher skills are in \`${configDir}/skills/co-researcher/\`
Use OpenCode's native \`skill\` tool to list and load these skills.

**Critical Rules:**
- Before ANY complex research task, examine your available skills.
- If a relevant skill exists (e.g., \`literature-review\`, \`critical-analysis\`), you MUST use it.
- Announce: "I am activating the [Skill Name] skill to [purpose]."
- Never present a bibliography you have not verified. The \`literature-review\` skill ships \`scripts/verify_citations.py\`; it resolves every citation against OpenAlex, Crossref, and Europe PMC, and exits nonzero on any fabricated, mismatched, or retracted reference.

**Prerequisite for the research toolchain:** the \`literature-review\` scripts run via \`uv\`. If \`uv --version\` fails, run \`bash scripts/setup.sh\` in the repo once.

${toolMapping}
</EXTREMELY_IMPORTANT>`;
    };

    return {
        // Use system prompt transform to inject bootstrap
        'experimental.chat.system.transform': async (_input, output) => {
            const bootstrap = getBootstrapContent();
            if (bootstrap) {
                (output.system ||= []).push(bootstrap);
            }
        }
    };
};
