# 06 — Security

## Threat model

| Vector | Risk | Mitigation |
|---|---|---|
| Network | N/A — no HTTP server anywhere. | **No open port.** The only channel is stdio to a child subprocess of Hermes' own process. No network surface to defend. |
| Persistent process | N/A — no long-running daemon. | Subprocess exists only for the duration of a call (or a resumed session) — minimal, bounded exposure. |
| Filesystem access | The documented "easy" option is `--dangerously-skip-permissions` — full filesystem access. | The permission-mode decision below applies regardless of transport. |
| Shell execution (Bash) | `claude` has the Bash tool available by default — a headless provider could let the model run arbitrary shell commands as a side effect of an ordinary chat call, unnoticed. | `CLAUDE_CLI_RESTRICTED` defaults to `true` — `--restricted` (drops Bash/PowerShell/REPL/WebFetch) is on by default. Confirmed empirically: doesn't break normal chat, and does block an explicit attempt to invoke Bash ("I don't have access to a Bash tool in this session"). Set `CLAUDE_CLI_RESTRICTED=false` for a deployment that wants the provider to act as a full agent. |
| Environment leakage | A subprocess inherits the parent's full environment unless filtered. | `process.build_subprocess_env()` is an allowlist (deny by default): only `HOME`, `PATH`, `LANG`/`LC_*`, `TERM`, `TMPDIR`, `USER`, `LOGNAME`, `SHELL` reach the subprocess — everything else from Hermes' environment is dropped. |
| **`ANTHROPIC_API_KEY` overrides OAuth/Max auth** | Confirmed empirically: if `ANTHROPIC_API_KEY` is present in the parent process's environment (e.g. because Hermes' own `anthropic` provider needs it) and reaches the `claude` subprocess, the CLI warns "another auth source is set and takes precedence over your claude.ai login" and tries to bill against that key instead of the Max subscription — silently defeating the entire point of this plugin. | This is *why* the environment filter above is an allowlist rather than a blocklist: a blocklist would have to guess `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, and every future Anthropic-specific variable. Tested with a deliberately invalid key in the parent env: without the fix the call hangs/errors; with it, OAuth is used normally. |
| Uncontrolled spend | No cap by default. | `--max-budget-usd` is available natively (see [04](./04-claude-cli-reference.md)) and exposed as `CLAUDE_CLI_MAX_BUDGET_USD`, though unset by default (no cap). |

## Permission-mode default

**Restrictive by default**, in two parts:

1. `CLAUDE_CLI_PERMISSION_MODE=auto` + `--permission-prompts none` always — anything that would need human confirmation is denied instead of hanging.
2. `CLAUDE_CLI_RESTRICTED=true` by default — drops Bash/PowerShell/REPL/WebFetch.

`PermissionConfig.bypass` (`--dangerously-skip-permissions`) still exists in `process.py` for a deployment that explicitly wants full-agent behavior, but there's no environment variable exposed for it — it's opt-in only by editing `client.py` directly, deliberately more friction than a plain env-var toggle would give.

**Under a multiplexed gateway, note that `CLAUDE_CLI_*` config (including any MCP bridge registered via `CLAUDE_CLI_MCP_CONFIG`/`CLAUDE_CLI_ALLOWED_TOOLS`) is shared by every profile using `claude-cli`** — see [05-configuration.md](./05-configuration.md#multiplexed-gateways-env-must-be-the-default-profiles). A bridge or elevated permission set meant for one profile is reachable, and acts as that profile, from any other profile's `claude-cli` turns on the same multiplexed gateway.

## `--add-dir` swallowing the prompt (fixed)

`--add-dir` is a variadic CLI flag. `build_args()` used to append the prompt right after it with no separator; a prompt not starting with `-` (the common case) was silently consumed as one more `--add-dir` value instead of reaching `claude`, failing with `Error: Input must be provided either through stdin or as a prompt argument`. Only manifested with `CLAUDE_CLI_ALLOWED_DIRS` set (empty by default, so earlier smoke tests missed it). Fixed by unconditionally inserting `--` before the prompt — not just when `allowed_dirs` is set, to guard against any future variadic flag too. Re-verified end-to-end with `CLAUDE_CLI_ALLOWED_DIRS` configured.

## Sensitive-content redaction: not implemented, deliberately

Tested empirically: the `claude` CLI does **not** redact secrets from files when explicitly asked to print raw content (verified with a fake API key and database password in a file, via `--add-dir` plus a prompt requesting the exact contents — both came back unredacted). The reference `copilot_acp_client.py` can redact because it *mediates* file access (it implements the ACP `fs/read_text_file` handler itself and intercepts content before the model sees it) — this plugin's subprocess architecture has no such interception point: `claude` reads files entirely inside its own process, using its own Read tool, without consulting us. The only redaction possible here would be scrubbing secret-shaped patterns from the final response text before returning it to Hermes — weaker (doesn't stop the model from having already "seen" the secret) and risks false positives on legitimate content (e.g. an answer that mentions an example API key format). Decision: not implemented — an accepted limitation, not an oversight. Revisit if this provider ever processes untrusted third-party files.

## Open hardening items (don't block shipping, but should be tracked)

- Path confinement (`_ensure_path_within_cwd` in the reference `copilot_acp_client.py` is a reasonable model) if this plugin ever needs to manipulate externally-supplied paths before passing them to the CLI.
- Log auditing: worth logging `model`, message count, and tool count per request for observability, without ever logging full prompt content (may contain sensitive user data).
- Concurrency around session continuity (Fase 4, `--resume`): the lock in `client.py` protects state read/write, but the CLI's own behavior under two genuinely concurrent calls resuming the same session hasn't been tested against a real race — see [08-roadmap.md](./08-roadmap.md).
