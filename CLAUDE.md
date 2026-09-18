# CLAUDE.md — hermes-claude-cli

Instruções de projeto para sessões do Claude Code trabalhando neste repositório. Leia isto antes de tocar em código.

## O que é este projeto

Plugin de provider de modelo para o **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** (Nous Research) que expõe o CLI oficial `claude` (Claude Code) autenticado via **assinatura Claude Max** como um provider de primeira classe (`hermes model` → "Claude CLI (Max subscription)").

Este repositório **substitui e unifica** dois repositórios de terceiros:
- [`niski84/claude-bridge`](https://github.com/niski84/claude-bridge) (servidor HTTP Go)
- [`niski84/hermes-claude-cli`](https://github.com/niski84/hermes-claude-cli) (plugin Python que dependia do bridge acima)

**Toda a análise que fundamenta as decisões abaixo está em [`docs/`](./docs/README.md). Leia `docs/README.md` primeiro para saber qual documento consultar.**

## Status atual

**Fase 1 implementada e testada** (2026-09-18): `plugin/claude_cli/{protocol,process,config,client,models,__init__}.py` funcionam de ponta a ponta contra o `claude` CLI real (smoke test manual confirmado — resposta correta, `usage`/custo reais, multi-turno, caminho de erro sem crash). 54 testes automatizados (`pytest`, nenhum chama o CLI real), `ruff check` limpo. Ambiente de dev: `.venv/` local via `uv` (`python3 -m venv` não funciona neste sistema — falta `python3-venv`).

Ver `docs/10-roadmap.md` (seção "Status" no topo) para o que exatamente foi feito e o que continua pendente (Fases 2–5). Código em inglês (comentários, docstrings, identificadores); esta documentação e a comunicação com o usuário continuam em português.

Rodar os testes:
```
cd /mnt/dev/projects-rk/hermes-claude-cli
.venv/bin/python -m pytest -q
```

## Decisão arquitetural central (não reabrir sem justificativa nova)

**Este plugin NÃO usa um servidor HTTP.** A tentação óbvia (replicar o `claude-bridge` como um servidor HTTP embutido) foi avaliada e rejeitada em [`docs/04-decisao-bridge-e-necessario.md`](./docs/04-decisao-bridge-e-necessario.md). Em vez disso, usa o mecanismo nativo do Hermes Agent para providers cujo protocolo não é HTTP:

- `ProviderProfile(auth_type="external_process", process_command="claude", ...)`
- `ProviderProfile.create_client()` sobrescrito para devolver um cliente customizado que fala com o `claude` CLI via subprocesso/stdio — **sem socket, sem porta**.
- Padrão de referência real, em produção no próprio Hermes Agent: `plugins/model-providers/copilot-acp/` + `agent/copilot_acp_client.py` (documentado em `docs/03-modelo-de-provider-do-hermes.md`).

Se uma sessão futura considerar "adicionar de volta um servidor HTTP", ela deve primeiro ler `docs/04-decisao-bridge-e-necessario.md` e `docs/09-escopo-e-migracao.md` — só há um cenário registrado onde isso faria sentido (reuso por ferramentas fora do Hermes), e está marcado como Fase 6 opcional, não padrão.

## Convenções do projeto

- **Um único repositório, uma única linguagem (Python).** Não introduzir Go, binários compilados, ou dependência de toolchains externas — era exatamente a complexidade que este projeto elimina.
- **Sem processos de longa duração.** O `claude` CLI é invocado como subprocesso por chamada (v1) ou por sessão (v2, ver roadmap) — nunca como daemon systemd.
- **Módulos pequenos e de responsabilidade única** dentro de `plugin/claude_cli/` (`client.py`, `protocol.py`, `process.py`, `config.py`, `models.py`) — ver layout completo em `docs/05-arquitetura-unificada.md`.
- **`.gitignore` estrito**: nunca versionar binários, arquivos `.pid`, ou artefatos de build. O repositório `claude-bridge` original cometeu esse erro (ver `docs/01-analise-claude-bridge.md`) — não repetir.
- **TDD** para qualquer lógica de tradução de mensagens (`protocol.py`) — escrever teste primeiro, seguindo o padrão AAA (Arrange-Act-Assert) das regras globais do usuário.
- **Não assumir modo de permissão permissivo por padrão.** A escolha entre `--dangerously-skip-permissions` (como o original) e um modo mais restritivo (`--permission-mode` + `--restricted`) é uma decisão em aberto documentada em `docs/08-seguranca.md` — não implementar um default sem revisitar esse documento.

## Antes de implementar qualquer coisa

1. Ler `docs/00-visao-geral.md` (premissas assumidas — em especial, que "Hermes" = Hermes Agent da Nous Research, não um produto interno).
2. Ler `docs/10-roadmap.md` — a Fase 0 lista decisões que precisam de validação do usuário antes de codar (nome final do pacote, licença, default de permissão).
3. Seguir a ordem de fases do roadmap — não pular para streaming (Fase 2) ou sessão contínua (Fase 4) antes de ter a Fase 1 (paridade funcional básica) testada.

## Referências externas usadas na análise (não copiar/colar sem verificar a versão)

- Código-fonte do Hermes Agent (`providers/base.py`, `providers/__init__.py`, `plugins/model-providers/copilot-acp/`, `agent/copilot_acp_client.py`) — analisado via clone raso em `github.com/NousResearch/hermes-agent`. Se uma sessão futura precisar reconsultar, os arquivos podem ter mudado desde então; reclonar e comparar antes de assumir que a API (`create_client`, `auth_type="external_process"`) continua idêntica.
- `claude --help` da versão **2.1.276** do Claude Code — flags relevantes documentadas em `docs/06-referencia-cli-claude.md`. Revalidar se a versão instalada mudar.
