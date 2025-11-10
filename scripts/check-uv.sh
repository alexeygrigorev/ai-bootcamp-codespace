#!/bin/bash
# Script to detect uv references and remind user to convert them

echo "🔍 Checking for uv references after merge..."

FOUND_UV=false

# Check for uv.lock files
if find . -name "uv.lock" -not -path "./.git/*" | grep -q .; then
    echo "⚠️  Found uv.lock files:"
    find . -name "uv.lock" -not -path "./.git/*"
    FOUND_UV=true
fi

# Check for PEP 621 format in pyproject.toml (indicates uv usage)
if grep -r "^\[project\]" --include="pyproject.toml" . 2>/dev/null | grep -v ".git" | grep -q .; then
    echo "⚠️  Found PEP 621 format pyproject.toml files (uv format):"
    grep -r "^\[project\]" --include="pyproject.toml" . 2>/dev/null | grep -v ".git" | cut -d: -f1 | sort -u
    FOUND_UV=true
fi

# Check for 'uv run' in common file types
if grep -r "uv run" --include="*.md" --include="*.py" --include="Makefile" . 2>/dev/null | grep -v ".git" | grep -q .; then
    echo "⚠️  Found 'uv run' commands in:"
    grep -r "uv run" --include="*.md" --include="*.py" --include="Makefile" . 2>/dev/null | grep -v ".git" | cut -d: -f1 | sort -u
    FOUND_UV=true
fi

if [ "$FOUND_UV" = true ]; then
    echo ""
    echo "📝 Action needed: Ask your AI assistant to convert uv to poetry"
    echo "   Example: 'convert any uv stuff to poetry' or 'clean up the merge'"
    exit 1
else
    echo "✅ No uv references found. All good!"
    exit 0
fi

