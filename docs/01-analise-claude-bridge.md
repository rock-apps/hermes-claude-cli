# 01 — Analysis: `niski84/claude-bridge`

Repository: https://github.com/niski84/claude-bridge (Go, MIT, ~9 commits).

A single-file Go HTTP server (~350 LOC, no external dependencies) exposing an OpenAI-compatible `/v1/chat/completions`, `/v1/models`, and `/api/health`. Each request runs `claude -p --print --model <alias> --safe-mode ... <prompt>` as a subprocess, waits for output, and returns it as an OpenAI-shaped response (or a faked 3-chunk SSE "stream").

## Why this project doesn't reuse that design

Hermes Agent's native `auth_type="external_process"` + `create_client()` extension point (used by the bundled `copilot-acp` provider) makes an HTTP server unnecessary — see [ADR 04](./04-decisao-bridge-e-necessario.md). Auditing the real Go source also surfaced problems worth not repeating:

- **Cost/usage accounting never actually worked.** The code declares a result struct with `TotalCostUSD`/`Usage`/`SessionID` fields, but the real CLI call never passes `--output-format json` — it treats stdout as plain text, so those fields are hardcoded to zero/generated locally. The README's advertised cost logging (`cost=$0.0705`) never reflected reality. This plugin fixes that by actually requesting and parsing `--output-format json`.
- **Streaming was fake.** No `--output-format stream-json`; "streaming" was one full response split into 3 SSE events after the CLI already finished. The `claude` CLI does support real incremental output (`stream-json --include-partial-messages`) — see [06](./06-referencia-cli-claude.md).
- **No auth, and the network bind was broader than documented.** `http.Server{Addr: ":9180"}` binds all interfaces, not just loopback, despite the README claiming "localhost only." Any local (or, without a firewall, network) process could spend the user's subscription. Irrelevant once there's no listening port at all.
- **Whole conversation history re-sent on every turn**, with no use of the CLI's own `--session-id`/`--resume` support — wastes input tokens on long conversations. This project's session-continuity feature (Fase 4, see [10-roadmap.md](./10-roadmap.md)) addresses that.
- A single "backup" commit also introduced two undocumented, unrelated binaries (`model-router`, `zai-proxy` — routing the *Claude Code CLI itself* to third-party models like DeepSeek/GLM) plus several binary/`.pid` artifacts that shouldn't have been committed. Out of scope here — see [09-escopo-e-migracao.md](./09-escopo-e-migracao.md).

## What was worth keeping

- Model alias normalization (`sonnet`/`opus`/`haiku` collapsing versioned IDs) — ported as-is.
- The idea of a configurable allowed-directories list for `--add-dir` — kept, without the original's hardcoded personal paths.
- Mapping `claude`'s `stop_reason` to an OpenAI `finish_reason` — ported as-is.
