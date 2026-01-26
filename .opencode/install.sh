#!/bin/bash

# OpenCode Extension Installer

CONFIG_DIR="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Installing Co-Researcher for OpenCode..."
echo "Repo Dir: $REPO_DIR"
echo "Config Dir: $CONFIG_DIR"

# 1. Install Plugin
mkdir -p "$CONFIG_DIR/plugins"
rm -f "$CONFIG_DIR/plugins/co-researcher.js"
ln -s "$REPO_DIR/.opencode/plugins/co-researcher.js" "$CONFIG_DIR/plugins/co-researcher.js"
echo "✅ Plugin linked."

# 2. Install Skills
mkdir -p "$CONFIG_DIR/skills"
rm -rf "$CONFIG_DIR/skills/co-researcher"
ln -s "$REPO_DIR/skills" "$CONFIG_DIR/skills/co-researcher"
echo "✅ Skills linked."

echo ""
echo "Installation complete! Restart OpenCode to activate."
