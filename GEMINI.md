# Co-Researcher Agents for Gemini

This project provides PhD-level research capabilities for your Gemini CLI sessions.

## Available Agents

### Available Skills
See `skills/` for the full list of capabilities, including:
- `research-methodology`
- `literature-review`
- `critical-analysis`
- `hypothesis-testing`
- `lateral-thinking`
- `qualitative-research`
- `quantitative-analysis`
- `peer-review`
- `ethics-review`
- `grant-writing`


## How to use in Gemini CLI

Gemini automatically discovers these agents when you run it from this directory. You can invoke them by name:

```bash
gemini "Use the literature-review skill to find recent papers on room temperature superconductors"
gemini "Ask the critical-analysis skill to review my methodology in proposal.md"
```

The CLI reads the context from `agents/` and this `GEMINI.md` file automatically.
It also has access to the specialized skills in the `skills/` directory.

### Available Skills
See `skills/` for the full list of capabilities, including:
- `research-methodology`
- `literature-review`
- `critical-analysis`

