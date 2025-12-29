# Publishing & Distribution Guide

This guide explains how to distribute and "publish" the Co-Researcher PhD suite so that other users can use it across Claude Code, Gemini CLI, and OpenAI Codex CLI.

## 1. Unified Distribution Model

The Co-Researcher plugin follows a **Repository-as-a-Plugin** model. All three platforms (Claude, Gemini, Codex) are designed to discover capabilities directly from the project's root and specialized metadata files.

To publish, you simply need to make this repository accessible to the target users (e.g., via a public GitHub repository).

## 2. Platform-Specific Discovery

### Claude Code
- **Discovery**: Claude Code automatically scans the `commands/` and `agents/` directories when it is initialized in a project.
- **How to Publish**: 
  1. Push your project to GitHub.
  2. Users can either clone the repo or use `claude add` (if supported in their environment) to point to your repository.
  3. No central registry is required; the directory structure handles the logic.

### Gemini CLI
- **Discovery**: Uses the `GEMINI.md` file at the root for project context and the `.gemini/commands/` directory for slash commands.
- **How to Publish**:
  1. Ensure `GEMINI.md` contains accurate descriptions of all 8 agents.
  2. When a user runs `gemini` inside this project directory, it will automatically index the PhD agents and enable commands like `/research` or `/review`.

### OpenAI Codex CLI
- **Discovery**: Uses the `AGENTS.md` manifest in the root and the `.codex/skills/` directory for repository-wide capabilities.
- **How to Publish**:
  1. Ensure `AGENTS.md` is in the root and contains your AI personality and research workflows.
  2. Users simply open the repository with Codex CLI. 
  3. No installation command is needed; the CLI automatically merges the local `AGENTS.md` with the user's global guidance and activates the skills.

## 3. Best Practices for Release

1. **Version Tags**: Use Git tags (e.g., `v1.2.0`) to mark stable releases.
2. **Evaluation Summary**: Always include a recent `evals/results/index.md` (or a link to it) so users can see the current accuracy scores for the agents.
3. **Multi-Model Config**: Remind users that while the suite is multi-model, results may vary. Recommend `claude-3-5-sonnet` (Claude Code), `gemini-1.5-pro` (Gemini CLI), or `gpt-4o` (Codex CLI) for PhD-level tasks.

## 4. Collaborative Publishing
If you wish to contribute these agents to a central PhD research community:
1. Submit a PR to the [Aletheia Marketplace](https://github.com/aletheia/marketplace) (if applicable).
2. Host the project as a GitHub Template so others can branch off for specific research domains (e.g., medical, legal).
