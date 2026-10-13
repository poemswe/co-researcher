#!/bin/bash
# Bump version across all project files and create git tag
# Usage: ./scripts/bump-version.sh <major|minor|patch>

set -e

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <major|minor|patch>"
    exit 1
fi

BUMP_TYPE=$1

# Get current version from plugin.json (macOS compatible)
CURRENT_VERSION=$(sed -n 's/.*"version":[[:space:]]*"\([^"]*\)".*/\1/p' .claude-plugin/plugin.json)
echo "Current version: $CURRENT_VERSION"

# Parse version components
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Bump version based on type
case $BUMP_TYPE in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
    *)
        echo "Invalid bump type. Use: major, minor, or patch"
        exit 1
        ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"
echo "New version: $NEW_VERSION"

# Update all version files
echo "Updating version files..."

sed -i.bak "s|badge/version-[0-9.]*-|badge/version-$NEW_VERSION-|" README.md && rm README.md.bak
for f in gemini-extension.json .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json; do
  sed -i.bak "s/\"version\": \"[0-9.]*\"/\"version\": \"$NEW_VERSION\"/" "$f" && rm "$f.bak"
done
sed -i.bak "s/\*\*Current Version: v[0-9.]*\*\*/**Current Version: v$NEW_VERSION**/" KnowledgeGraph.md && rm KnowledgeGraph.md.bak
sed -i.bak "s/\"softwareVersion\": \"[0-9.]*\"/\"softwareVersion\": \"$NEW_VERSION\"/; s/Co-Researcher v[0-9.]* —/Co-Researcher v$NEW_VERSION —/" index.html && rm index.html.bak

echo "✅ Version updated to $NEW_VERSION in all files"
echo ""
echo "Next steps:"
echo "  1. Review changes: git diff"
echo "  2. Commit: git add . && git commit -m \"chore: bump version to $NEW_VERSION\""
echo "  3. Tag: git tag -a v$NEW_VERSION -m \"Release v$NEW_VERSION\""
echo "  4. Push: git push && git push --tags"
