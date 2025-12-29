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
- **Discovery**: Uses the `gemini-extension.json` manifest and the `commands/` directory.
- **How to Publish**:
  1. Ensure `gemini-extension.json` is in the root.
  2. Users can install directly via Git:
     ```bash
     gemini extensions install https://github.com/your-username/co-researcher
     ```
  3. Commands like `/research` and `/review` will be available globally.

### OpenAI Codex CLI
- **Discovery**: Uses `AGENTS.md` at the root for agent behavior mapping and the `.codex/skills/` directory for repository-wide skills.
- **How to Publish**:
  1. Ensure `AGENTS.md` is formatted correctly for agent discovery.
  2. When the user opens the project with Codex CLI, it will detect the skills (e.g., `$review`, `$ethics`) and offer them as native operational capabilities.

## 3. Best Practices for Release

1. **Version Tags**: Use Git tags (e.g., `v1.2.0`) to mark stable releases.
2. **Evaluation Summary**: Always include a recent `evals/results/index.md` (or a link to it) so users can see the current accuracy scores for the agents.
3. **Multi-Model Config**: Remind users that while the suite is multi-model, results may vary. Recommend `claude-3-5-sonnet` or `gemini-1.5-pro` for PhD-level tasks.

## 4. Collaborative Publishing
If you wish to contribute these agents to a central PhD research community:
1. Submit a PR to the [Aletheia Marketplace](https://github.com/aletheia/marketplace) (if applicable).
2. Host the project as a GitHub Template so others can branch off for specific research domains (e.g., medical, legal).
