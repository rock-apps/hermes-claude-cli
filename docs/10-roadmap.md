# 10 — Roadmap

## Status

**Fase 1 implementada e verificada com E2E real dentro do Hermes Agent** (2026-09-18). Ver "Decisões tomadas durante a Fase 1" abaixo para como as questões abertas da Fase 0 foram resolvidas na prática — nenhuma delas bloqueou a implementação, mas ficam registradas para o usuário confirmar ou revisar. Fases 2+ continuam como plano, não executadas.

## ⚠️ Requisito de versão do Hermes Agent (achado em 2026-09-18, ao instalar no ambiente real do usuário)

Este plugin depende de `ProviderProfile.create_client()` + o campo `process_command` (e correlatos: `process_args`, `process_command_env_vars`, `process_args_env_var`) em `providers/base.py`. Esse mecanismo genérico **não existe em versões mais antigas do Hermes Agent** — nelas, o provider `copilot-acp` (nosso modelo de referência) é despachado por um `if` hardcoded por nome/`base_url` dentro de `agent/agent_runtime_helpers.py` (`if agent.provider == "copilot-acp" or base_url.startswith("acp://copilot")`), não por um hook genérico.

Confirmado na prática: a validação E2E da Fase 1 usou um **clone fresco da `main`** (tem o mecanismo genérico, plugin funciona). Ao instalar o mesmo plugin no Hermes Agent real já instalado neste ambiente (checkout de 2026-07-17, ~37.000 commits atrás da `main`), o carregamento do plugin falhou com:
```
Failed to load user provider plugin claude-cli: ProviderProfile.__init__() got an unexpected keyword argument 'process_command'
```

**Isso não é um bug do plugin** — é um requisito mínimo de versão que não existia quando o projeto começou (o mecanismo genérico é relativamente novo no histórico do Hermes Agent). Diagnóstico rápido em qualquer checkout do Hermes: `grep process_command providers/base.py` (presente = compatível).

**Correção**: `hermes update` (comando oficial, testado e disponível — `hermes --help` lista `update: Update Hermes Agent to the latest version`). **Não executado automaticamente** — é uma atualização grande (dezenas de milhares de commits) num ambiente pessoal já em uso ativo (sessões, cron jobs, integrações WhatsApp/Slack configuradas), decisão que cabe ao usuário, não a uma sessão automatizada.

### Validação E2E real (não só testes unitários isolados)

Clone completo e real de `NousResearch/hermes-agent`, ambiente próprio (`uv sync`), `HERMES_HOME` isolado, plugin symlinkado em `plugins/model-providers/claude-cli` exatamente como o instalador original fazia — e o comando de verificação oficial deles rodado de verdade:

```
$ python -m hermes_cli.main -z "What is the capital of Portugal? One word." --provider claude-cli -m sonnet
Lisboa
```

Isso prova que o mecanismo de descoberta de provider do Hermes de verdade encontra nosso plugin e roteia uma chamada real através dele — não só que nosso `ClaudeCLIClient` funciona quando chamado diretamente pelos nossos próprios testes.

**Dois bugs reais encontrados e corrigidos** — só apareceram porque o Hermes chama o client do jeito que ele chama de verdade, não do jeito que nós supúnhamos:

1. **Timeout**: o Hermes passa `timeout` como um objeto tipo `httpx.Timeout` (tem `.read`/`.write`/`.connect`/`.pool`), não como `float`. Isso quebrava `subprocess.run(timeout=...)`. Corrigido com `_effective_timeout()` em `client.py` (mesma solução que o `copilot_acp_client.py` de referência usa para o mesmo problema).
2. **Streaming**: o relay interno do Hermes sempre chama em modo streaming e espera `.choices[i].delta`, não `.choices[i].message`. Corrigido usando o mesmo helper que o `copilot-acp` de referência usa: `agent.acp_openai_bridge.completion_to_stream_chunks(completion)`.

Também foi adicionado um `close()` no-op em `ClaudeCLIClient` (o Hermes chama `close()` incondicionalmente no cleanup de todo client de provider).

Suíte de testes ampliada para cobrir os dois casos (60 testes agora, incluindo um módulo `agent.acp_openai_bridge` falso injetado via `sys.modules` para testar a conversão de streaming sem precisar de um checkout real do Hermes). `pytest -q` → `60 passed`, `ruff check` limpo.

## Fase 0 — Decisões que estavam abertas antes de codar

1. ~~Confirmar a premissa de "Hermes" = Hermes Agent (NousResearch)~~ — mantida como estava assumida; a implementação depende disso (`from providers import register_provider`), então se estiver errada, `plugin/claude_cli/__init__.py` precisa mudar.
2. ~~Escolher o default de `CLAUDE_CLI_PERMISSION_MODE`~~ — **resolvido**: default `"auto"` (o modo de auto-aprovação nativo do próprio Claude Code, o mesmo sob o qual esta sessão de desenvolvimento rodou), sempre combinado com `--permission-prompts none` (nada que pediria confirmação humana trava — é negado, já que não há humano para responder num provider headless). Ver `plugin/claude_cli/config.py` e [08-seguranca.md](./08-seguranca.md). Ajustável via `CLAUDE_CLI_PERMISSION_MODE`.
3. Nome final do pacote/plugin — mantido `claude-cli` (paridade com o original). Não revisitado.
4. Licença do repositório — **ainda não decidido**, nenhum arquivo `LICENSE` foi criado. Continua em aberto.

## Fase 1 — Provider mínimo funcional (paridade v1) — ✅ implementada

Implementado e testado (54 testes, `pytest -q` → `54 passed`; `ruff check` limpo):

- `plugin/claude_cli/protocol.py` — achatamento de mensagens, normalização de alias de modelo, mapeamento de `stop_reason` (23 testes).
- `plugin/claude_cli/process.py` — `build_args`/`run_once` via `--output-format json`, com parsing real de `total_cost_usd`/`usage`/`session_id`/`is_error` (corrige o bug descrito em [01](./01-analise-claude-bridge.md)) — schema verificado empiricamente contra o `claude` CLI real instalado (v2.1.276), não assumido (14 testes, subprocess real fake, nunca chama o CLI de verdade nos testes).
- `plugin/claude_cli/config.py` — leitura de variáveis de ambiente conforme [07-configuracao.md](./07-configuracao.md) (9 testes).
- `plugin/claude_cli/client.py` — `ClaudeCLIClient`, facade `.chat.completions.create(...)` (8 testes).
- `plugin/claude_cli/__init__.py` — registro do `ProviderProfile` com `auth_type="external_process"`, import de `providers` guardado (não quebra fora de um processo Hermes real) (1 teste).
- `plugin/claude_cli/models.py` — catálogo estático de modelos.
- **Smoke test manual real** (não automatizado, para não gastar uso a cada `pytest`): chamada completa via `ClaudeCLIClient` real contra o `claude` CLI de verdade — resposta correta, system prompt respeitado, `usage`/`cost_usd` populados com valores reais (não mais zerados), conversa multi-turno preservando contexto, e caminho de erro (modelo inválido) tratado sem crash (`is_error=True`, mensagem legível). Comando usado para reproduzir manualmente:
  ```
  PYTHONPATH=. .venv/bin/python -c "from plugin.claude_cli.client import ClaudeCLIClient; ..."
  ```
- Ambiente de dev: `.venv/` local (via `uv venv` + `uv pip install pytest ruff`; `python3 -m venv` falhou neste sistema por falta do pacote `python3-venv`).

## Fase 2 — Streaming real

**Decisão revisada durante a Fase 1**: não implementar um parser incremental de `stream-json` dedicado (`run_streaming`/`StreamChunk`) como planejado originalmente. Ao investigar o repositório de referência real da Nous Research (`agent/copilot_acp_client.py`, o provider `copilot-acp` bundled no Hermes), descobriu-se que **mesmo o cliente de referência oficial não faz streaming incremental de verdade** para um provider baseado em subprocesso — ele monta a resposta completa e converte para chunks via um helper compartilhado do próprio Hermes (`agent.acp_openai_bridge.completion_to_stream_chunks`). `client.py` já implementa essa mesma estratégia (`stream=True` retorna `iter([completion])`, uma única resposta completa como "stream" de um chunk) e está marcado com um comentário apontando para esta seção.

Trabalho real desta fase, se for adotado no futuro: usar `--output-format stream-json --include-partial-messages` (schema de eventos já capturado e verificado — ver [06-referencia-cli-claude.md](./06-referencia-cli-claude.md)) e, em vez de reinventar o formato de chunk, chamar `agent.acp_openai_bridge.completion_to_stream_chunks` (ou o helper de streaming real equivalente, se o Hermes tiver um) a partir de eventos incrementais em vez de uma única `CLIResult` final — precisa investigar se esse helper aceita um iterador incremental ou só uma `completion` já pronta antes de prometer token-a-token de verdade.

## Fase 3 — Hardening de segurança — ✅ parcialmente implementada (2026-09-18)

- ~~Implementar o modo de permissão decidido na Fase 0~~ — feito na Fase 1.
- ~~Filtragem explícita do ambiente repassado ao subprocesso~~ — **feito**: `process.build_subprocess_env()` (allowlist: `HOME`, `PATH`, `LANG`/`LC_*`, `TERM`, `TMPDIR`, `USER`, `LOGNAME`, `SHELL`), chamado por `client.py` em toda invocação. **Achado crítico durante a implementação, não previsto no plano original**: `ANTHROPIC_API_KEY`, se repassada ao subprocesso, sobrescreve silenciosamente a autenticação OAuth/Max e faz o CLI tentar faturar pela API key — verificado empiricamente (com uma chave inválida de propósito: sem a correção a chamada trava; com a correção, ignora a variável e funciona via OAuth normalmente). Ver [08-seguranca.md](./08-seguranca.md). 4 novos testes (`TestBuildSubprocessEnv` em `test_process.py` + 1 em `test_client.py`), suíte total agora com 65 testes.
- ~~Revisão de redação de conteúdo sensível~~ — **feito**: testado empiricamente que o `claude` CLI não redige segredos, e que nossa arquitetura de subprocesso não tem ponto de interceptação para fazer isso do jeito que o `copilot_acp_client.py` de referência faz (ele medeia acesso a arquivo via ACP; nós não). Decisão: não implementar raspagem de saída por enquanto (risco de falso positivo > benefício). Ver [08-seguranca.md](./08-seguranca.md).
- **Bug real encontrado e corrigido nesta fase** (fora do escopo original, achado ao testar `--add-dir` manualmente): `--add-dir` é variádico no CLI — sem um separador `--` antes do prompt, um prompt que não começa com `-` era silenciosamente engolido como mais um diretório, e a chamada falhava com "Input must be provided...". Só se manifestava com `CLAUDE_CLI_ALLOWED_DIRS` configurado (por isso não apareceu antes). Corrigido em `build_args()` (`--` sempre antes do prompt). Testado de verdade com `CLAUDE_CLI_ALLOWED_DIRS` configurado, pós-correção — funciona. 2 novos testes de regressão, suíte agora com 67 testes.
- **Ainda não feito**: `--restricted` como possível default (hoje `false`, configurável via `CLAUDE_CLI_RESTRICTED`); `--max-budget-usd` sem default definido (hoje sem teto). Nenhum dos dois é um bug — são só ajustes de postura de segurança ainda não decididos, não bloqueiam nada.

## Fase 4 — Sessão contínua (v2, otimização)

- Mapear sessão do Hermes ⇄ `--session-id`/`--resume` do `claude` CLI, evitando reenviar o histórico completo a cada turno.
- Testar cenários de expiração/compactação de sessão e concorrência (chamadas simultâneas na mesma sessão).

## Fase 5 — Empacotamento e distribuição — ✅ parcialmente implementada (2026-09-18)

- ~~Script de instalação simplificado~~ — **feito**: `scripts/install.sh` — symlinka `plugin/claude_cli/` em `$HERMES_HOME/plugins/model-providers/claude-cli`, sem clone de segundo repositório, sem `go build`, sem systemd. Testado num `HERMES_HOME` descartável, inclusive idempotência (rodar duas vezes não quebra).
- ~~Documentação de usuário final~~ — **feito**: `README.md` atualizado com instalação e status real.
- **Descoberta**: esta própria máquina de desenvolvimento já tem um Hermes Agent real instalado (`hermes` no PATH, v0.18.2, em `~/.hermes/hermes-agent`) — separado do sandbox descartável usado na validação E2E da Fase 1. Instalar o plugin aí de verdade (rodando `./scripts/install.sh` sem `HERMES_HOME` customizado) é possível a qualquer momento, mas é uma ação fora deste repositório, em ambiente já em uso — não feito automaticamente, fica para quando o usuário pedir explicitamente.
- **Ainda não feito**: avaliar `pyproject.toml` + entry point `hermes_agent.plugins` como alternativa ao symlink manual (ver [03](./03-modelo-de-provider-do-hermes.md)) — o symlink já está validado E2E e funcionando; entry point fica como evolução opcional, não bloqueia nada.

## Fase 6 (opcional, sob demanda) — Modo HTTP dual

Só se surgir um requisito real de reuso do "bridge" por ferramentas fora do Hermes (Open WebUI, Cursor, etc., como o `claude-bridge` original permitia). Ver alternativa rejeitada em [04-decisao-bridge-e-necessario.md](./04-decisao-bridge-e-necessario.md#alternativa-considerada-e-rejeitada-para-v1). Não implementar preventivamente (YAGNI).

## Fora de escopo permanente (a menos que explicitamente solicitado)

`model-router` e `zai-proxy` (trocar o backend de modelo do próprio Claude Code por DeepSeek/z.ai) — ver justificativa em [09-escopo-e-migracao.md](./09-escopo-e-migracao.md). Se a Rock Apps quiser isso, deve nascer como projeto/decisão separada, não como parte deste plugin.
