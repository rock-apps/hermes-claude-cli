#!/usr/bin/env bash
# hermes-claude-cli installer.
#
# Symlinks the claude-cli provider plugin into a Hermes Agent installation. No HTTP
# bridge, no second repository to clone, no Go toolchain, no systemd unit — see
# docs/04-decisao-bridge-e-necessario.md for why this project doesn't need any of
# that (unlike the two third-party projects it replaces).
#
# Prerequisites:
#   1. Claude Code CLI, authenticated with a Claude Max subscription. Offered
#      below via the official installer if missing; you still need to run
#      `claude` once yourself afterwards to log in.
#   2. Hermes Agent installed — this script does NOT install or bootstrap Hermes
#      itself (it has its own installer, e.g. setup-hermes.sh / hermes_bootstrap.py
#      in its repo: https://github.com/NousResearch/hermes-agent). Run that first.
#
# What this script does NOT install, and why:
#   - Python: not needed separately — the plugin runs inside Hermes Agent's own
#     already-running Python process, not as a standalone program.
#   - tmux: unrelated to this plugin. If you use tmux to manage Claude Code CLI
#     sessions, that's a separate personal workflow choice, not a dependency here.

set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PLUGIN_DIR="$HERMES_HOME/plugins/model-providers/claude-cli"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE_CODE_INSTALLER_URL="https://claude.ai/install.sh"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
fail() { echo -e "${RED}✗${NC} $*" >&2; exit 1; }

echo "-> Preflight checks"
if ! command -v claude >/dev/null 2>&1; then
    warn "Claude Code CLI not found."
    if [ -t 0 ]; then
        read -rp "Install it now via the official installer ($CLAUDE_CODE_INSTALLER_URL)? [y/N] " reply
    else
        reply="n"
    fi
    if [[ "$reply" =~ ^[Yy]$ ]]; then
        curl -fsSL "$CLAUDE_CODE_INSTALLER_URL" | bash
        command -v claude >/dev/null 2>&1 \
            || fail "Claude Code install did not complete. Install manually: https://claude.ai/code"
        warn "Run 'claude' once to log in with your Claude Max subscription before using this plugin."
    else
        fail "Claude Code CLI is required. Install from https://claude.ai/code (or re-run this script and answer 'y'), then authenticate with 'claude' before continuing."
    fi
fi
ok "claude CLI: $(claude --version 2>&1 | head -1 || echo present)"

[ -d "$HERMES_HOME" ] \
    || fail "Hermes Agent not found at $HERMES_HOME. This script does not install Hermes itself — run its own installer first (https://github.com/NousResearch/hermes-agent), or set HERMES_HOME to point at an existing install."
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
