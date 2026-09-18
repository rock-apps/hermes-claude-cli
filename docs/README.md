# Documentação — hermes-claude-cli

Índice de leitura recomendado, em ordem:

| # | Documento | Conteúdo |
|---|-----------|----------|
| 00 | [Visão geral](./00-visao-geral.md) | Objetivo do projeto, contexto, premissas assumidas |
| 01 | [Análise: claude-bridge](./01-analise-claude-bridge.md) | Engenharia reversa completa do repo `niski84/claude-bridge` |
| 02 | [Análise: hermes-claude-cli (original)](./02-analise-hermes-claude-cli-original.md) | Engenharia reversa completa do repo `niski84/hermes-claude-cli` |
| 03 | [Como o Hermes Agent trata providers](./03-modelo-de-provider-do-hermes.md) | Engenharia reversa do mecanismo de plugins de provider do `NousResearch/hermes-agent` (fonte primária, não documentação de terceiros) |
| 04 | [Decisão: o bridge é necessário?](./04-decisao-bridge-e-necessario.md) | ADR respondendo diretamente à pergunta do usuário |
| 05 | [Arquitetura unificada](./05-arquitetura-unificada.md) | Design do plugin único que substitui os dois repositórios |
| 06 | [Referência: flags relevantes do CLI `claude`](./06-referencia-cli-claude.md) | Levantamento das flags do `claude` CLI que a integração depende |
| 07 | [Configuração](./07-configuracao.md) | Variáveis de ambiente e superfície de configuração do plugin unificado |
| 08 | [Segurança](./08-seguranca.md) | Modelo de ameaça e mitigação, comparando bridge HTTP vs. subprocesso direto |
| 09 | [Escopo e migração](./09-escopo-e-migracao.md) | O que é herdado, o que é descartado (e por quê) dos dois repositórios originais |
| 10 | [Roadmap](./10-roadmap.md) | Fases de implementação propostas |

## Status

Fase atual: **análise + arquitetura** (nenhum código funcional foi implementado ainda). Ver [10-roadmap.md](./10-roadmap.md) para as próximas fases.
