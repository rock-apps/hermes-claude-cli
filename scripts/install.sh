#!/usr/bin/env bash
# hermes-claude-cli installer.
#
# Symlinks the claude-cli provider plugin into a Hermes Agent installation. No HTTP
# bridge, no second repository to clone, no Go toolchain, no systemd unit — see
# docs/04-decisao-bridge-e-necessario.md for why this project doesn't need any of
# that (unlike the two third-party projects it replaces).
#
# Prerequisites:
#   1. Claude Code CLI installed and authenticated: https://claude.ai/code
#   2. Hermes Agent installed: https://github.com/NousResearch/hermes-agent

set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PLUGIN_DIR="$HERMES_HOME/plugins/model-providers/claude-cli"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
fail() { echo -e "${RED}✗${NC} $*" >&2; exit 1; }

echo "-> Preflight checks"
command -v claude >/dev/null 2>&1 \
    || fail "Claude Code CLI not found. Install from https://claude.ai/code first."
ok "claude CLI: $(claude --version 2>&1 | head -1 || echo present)"

[ -d "$HERMES_HOME" ] \
    || fail "Hermes Agent not found at $HERMES_HOME. Install it first (https://github.com/NousResearch/hermes-agent), or set HERMES_HOME to point at an existing install."
ok "Hermes Agent: $HERMES_HOME"

echo "-> Plugin"
mkdir -p "$(dirname "$PLUGIN_DIR")"
if [ -e "$PLUGIN_DIR" ] || [ -L "$PLUGIN_DIR" ]; then
    rm -rf "$PLUGIN_DIR"
fi
ln -s "$REPO_DIR/plugin/claude_cli" "$PLUGIN_DIR"
ok "plugin symlinked: $PLUGIN_DIR -> $REPO_DIR/plugin/claude_cli"

echo "-> Verifying"
if command -v hermes >/dev/null 2>&1; then
    ok "hermes CLI found on PATH"
else
    warn "hermes CLI not found on PATH — the plugin is symlinked; verify from inside your Hermes Python environment instead, e.g.:"
    echo "      python -m hermes_cli.main -z \"hello\" --provider claude-cli -m sonnet"
fi

cat <<'EOF'

──────────────────────────────────────────────────────────────────
Install complete. No HTTP bridge, no build step, no systemd unit — the
plugin talks to `claude` as a direct subprocess.

Next:
  hermes model
  (look for "Claude CLI (Max subscription)")

Or verify directly:
  python -m hermes_cli.main -z "hello" --provider claude-cli -m sonnet

Configuration (all optional, see docs/07-configuracao.md):
  CLAUDE_CLI_BIN, CLAUDE_CLI_DEFAULT_MODEL, CLAUDE_CLI_ALLOWED_DIRS,
  CLAUDE_CLI_PERMISSION_MODE, CLAUDE_CLI_RESTRICTED,
  CLAUDE_CLI_MAX_BUDGET_USD, CLAUDE_CLI_TIMEOUT_SECONDS
──────────────────────────────────────────────────────────────────
EOF
