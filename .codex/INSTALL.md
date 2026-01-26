# Installing Co-Researcher for Codex

## 1. Environment Setup

Ensure you have Node.js installed.

## 2. Clone the Repository

Clone this repository to a standard location (e.g., `~/.codex/co-researcher`):

```bash
mkdir -p ~/.codex
cd ~/.codex
git clone <repo-url> co-researcher
```

## 3. Register the Hook

Update your `~/.codex/AGENTS.md` to include this section:

```markdown
## Co-Researcher System

<EXTREMELY_IMPORTANT>
You have Co-Researcher skills. RIGHT NOW run: `~/.codex/co-researcher/.codex/co-researcher-codex bootstrap` and follow the instructions it returns.
</EXTREMELY_IMPORTANT>
```

## 4. Verification

Restart Codex and run:

```bash
~/.codex/co-researcher/.codex/co-researcher-codex bootstrap
```

It should output the bootstrap instructions and list available skills.
