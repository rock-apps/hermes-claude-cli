# 02 — Analysis: `niski84/hermes-claude-cli` (third-party original)

Repository: https://github.com/niski84/hermes-claude-cli (Python, MIT, 2 commits) — the third-party project this repo's name comes from and replaces. Not to be confused with this repository (`rock-apps/hermes-claude-cli`).

A small Hermes plugin (`plugin/claude-cli/__init__.py`, ~85 lines) registering an OpenAI-style `ProviderProfile` pointed at `claude-bridge`'s HTTP endpoint, using Hermes' plain "fast path" for OpenAI-compatible providers (no custom client, implicit `api_mode="chat_completions"`). Its `env_vars=("CLAUDE_BRIDGE_URL",)` was a workaround, not a real credential — needed only because Hermes' provider picker requires at least one env var present to show a provider as "configured."

The plugin code itself was fine for the model it assumed (provider = OpenAI-compatible HTTP endpoint). The real cost was its `scripts/install.sh`: clone a second repository (`claude-bridge`), build it with Go, install a systemd user service to keep it running, symlink the plugin, and write a fake env var into Hermes' config — all just to satisfy "a provider needs an HTTP `base_url`." Its own README even listed "direct subprocess support, skipping the HTTP hop" as unimplemented future work — which is exactly the gap Hermes Agent's `auth_type="external_process"` mechanism already closes (see [03](./03-modelo-de-provider-do-hermes.md)), just not documented publicly when that project was written.

## What this project kept

- The core idea: a `ProviderProfile` with friendly aliases (`claude`, `claude-code`, `claude-max`).
- The curated model list (`sonnet`/`opus`/`haiku` + versioned IDs) — needs the same ongoing manual maintenance any Hermes provider requires as Anthropic ships new models.
- `default_aux_model="haiku"`.
- A post-install verification/smoke-test step.

## What this project dropped

- The second-repository dependency at install time.
- The systemd unit — there's no persistent bridge process to keep alive.
- The `CLAUDE_BRIDGE_URL` fake-credential workaround — replaced by `auth_type="external_process"`, which has correct, native semantics for this case (same pattern as Hermes' bundled `copilot-acp` provider).
