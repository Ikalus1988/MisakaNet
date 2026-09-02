#!/usr/bin/env bash
# setup-dev.sh — Install pre-commit hooks for local development
#
# Usage:
#   ./scripts/setup-dev.sh
#
# Requires:
#   - Python 3.10+
#   - pip or uv
set -euo pipefail

echo "🔧 Setting up MisakaNet development environment..."

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "❌ python3 not found. Install Python 3.10+ first."
  exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅ Python $PYTHON_VERSION"

# Install pre-commit if not present
if ! command -v pre-commit &>/dev/null; then
  echo "📦 Installing pre-commit..."
  if command -v uv &>/dev/null; then
    uv tool install pre-commit
  else
    pip install pre-commit
  fi
fi

echo "✅ pre-commit $(pre-commit --version)"

# Install hooks
echo "🪝 Installing pre-commit hooks..."
pre-commit install

# Validate lessons script exists
if [ ! -f "scripts/validate_lessons.py" ]; then
  echo "⚠️  scripts/validate_lessons.py not found — lesson validation hook may fail"
fi

if [ ! -f "scripts/check_lesson_quality.py" ]; then
  echo "⚠️  scripts/check_lesson_quality.py not found — lesson quality hook may fail"
fi

echo ""
echo "✅ Development environment ready!"
echo ""
echo "Hooks will run automatically on 'git commit'."
echo "To run manually: pre-commit run --all-files"
echo "To skip hooks:   git commit --no-verify"
