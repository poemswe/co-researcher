# Co-Researcher Agents for Gemini

This project provides PhD-level research capabilities for your Gemini CLI sessions.

## Available Skills

The extension provides specialized research skills in the `skills/` directory. Each skill has a SKILL.md file containing:
- YAML frontmatter with name, description, and required tools
- Role definition
- Principles and protocols to follow
- Specific workflows and output formats

### Core Research Skills
- **research-manager** - Start new research projects, manage complex multi-step workflows
- **research-methodology** - Select and validate appropriate research designs
- **literature-review** - Synthesize knowledge, identify gaps, trace scientific evolution
- **critical-analysis** - Analyze claims, evaluate evidence, identify fallacies
- **systematic-review** - Conduct PRISMA-standard systematic reviews
- **research-synthesis** - Merge findings into coherent narratives

### Analysis Skills
- **hypothesis-testing** - Formulate testable hypotheses, design experimental controls
- **quantitative-analysis** - Select statistical tests, interpret effect sizes
- **qualitative-research** - Design qualitative studies, perform thematic analysis

### Review & Ethics Skills
- **peer-review** - Critique manuscripts, evaluate methodological rigor
- **ethics-review** - Identify ethical risks, prepare IRB applications

### Creative & Strategic Skills
- **lateral-thinking** - Cross-domain analogies, first-principles reasoning
- **grant-writing** - Draft compelling grant proposals (NSF, NIH, ERC)

### Investigation Skills
- **multi-source-investigation** - Investigate claims across diverse sources
- **using-co-researcher** - Understand capabilities and system rules

## How Commands Work

Commands like `/research`, `/methodology`, `/analyze` automatically instruct you to read the appropriate skill file and follow its protocol. The skill files are located in the extension's `skills/` directory.

When executing a command:
1. You'll be instructed to read a specific skill file (e.g., `skills/research-manager/SKILL.md`)
2. Read the skill file using your available file reading tools
3. Follow the role, principles, and protocol defined in that skill
4. Apply the skill's guidelines to the user's request

