# hermes-claude-cli

Plugin de provider de modelo para o [Hermes Agent](https://github.com/NousResearch/hermes-agent) que expõe o CLI oficial `claude` (Claude Code), autenticado via assinatura **Claude Max**, como um provider de primeira classe — sem servidor HTTP intermediário.

> **Status**: em fase de análise e arquitetura. Ainda não há implementação funcional. Veja [`docs/README.md`](./docs/README.md) para a documentação completa (análise dos projetos de referência, decisões de arquitetura, roadmap) e [`CLAUDE.md`](./CLAUDE.md) para o resumo orientado a quem for implementar.

## Por quê

Ferramentas de terceiro que falam a API da Anthropic via chave de API (ou OAuth de terceiro) cobram do "extra usage" da assinatura Claude Max, não da franquia base do plano — o CLI oficial `claude` é o único caminho que usa a franquia base. Este plugin permite que o Hermes Agent use esse caminho.

## Documentação

Comece por [`docs/README.md`](./docs/README.md). Destaques:

- [`docs/04-decisao-bridge-e-necessario.md`](./docs/04-decisao-bridge-e-necessario.md) — por que este projeto **não** usa um servidor HTTP (diferente dos projetos que o inspiraram).
- [`docs/05-arquitetura-unificada.md`](./docs/05-arquitetura-unificada.md) — arquitetura proposta.
- [`docs/10-roadmap.md`](./docs/10-roadmap.md) — plano de implementação por fases.

## Projetos de referência analisados

- [`niski84/claude-bridge`](https://github.com/niski84/claude-bridge)
- [`niski84/hermes-claude-cli`](https://github.com/niski84/hermes-claude-cli)
