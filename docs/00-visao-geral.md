# 00 — Visão geral

## Objetivo

Consolidar em **um único projeto/plugin**, hospedado neste repositório (`rock-apps/hermes-claude-cli`), a funcionalidade hoje espalhada em dois repositórios públicos de terceiros:

- [`niski84/claude-bridge`](https://github.com/niski84/claude-bridge) — servidor HTTP em Go que expõe uma API compatível com OpenAI (`/v1/chat/completions`) na frente e roda o CLI oficial `claude` como subprocesso atrás.
- [`niski84/hermes-claude-cli`](https://github.com/niski84/hermes-claude-cli) — plugin Python para o [Hermes Agent](https://github.com/NousResearch/hermes-agent) que registra um provider `claude-cli` apontando para o `claude-bridge` acima.

Objetivo final do usuário original de ambos os repos: usar a assinatura **Claude Max** (via `claude` CLI autenticado) como um provider de modelo de primeira classe dentro do Hermes Agent, evitando cobrança por "extra usage" que ocorre quando se acessa a API da Anthropic via chave de API/OAuth de terceiros.

## Pergunta central feita pelo usuário

> "De repente esse bridge não é preciso. Ou é. Analise."

Resposta curta (detalhada no [ADR 04](./04-decisao-bridge-e-necessario.md)): **a função** do bridge (traduzir um protocolo HTTP compatível com OpenAI para uma chamada do CLI `claude`) **é necessária**, porque o Hermes exige que todo provider fale HTTP. Mas a **implementação atual** do bridge — um binário Go separado, em outro repositório, rodando como serviço systemd, escutando em uma porta TCP sem autenticação — **não é necessária**. O Hermes Agent já tem um mecanismo oficial e testado em produção (`ProviderProfile.create_client()` + `auth_type="external_process"`) desenhado exatamente para "providers que não falam HTTP" — usado hoje pelo provider bundled `copilot-acp`. Isso permite embutir toda a lógica de tradução dentro do próprio plugin Python, como um subprocesso local via stdio, **sem nenhum servidor HTTP, porta ou processo systemd separado**.

## Premissas assumidas (a validar com o usuário)

1. **"Hermes" = [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research)**, o mesmo framework referenciado nos dois repositórios analisados. Não foi encontrado nenhum produto interno da Rock Apps chamado "Hermes" (organização GitHub `rock-apps` não tem outro repositório com esse nome; memória de projeto não tem registro anterior). Se "Hermes" se referir a outra coisa, esta análise e a arquitetura proposta precisam ser revistas.
2. Este repositório (`rock-apps/hermes-claude-cli`) será o **plugin único e definitivo**, substituindo a necessidade de manter/clonar `niski84/claude-bridge` e `niski84/hermes-claude-cli` separadamente.
3. O ambiente-alvo tem o **Claude Code CLI (`claude`)** instalado e autenticado via assinatura Max (mesmo pré-requisito dos projetos originais).
4. Licença, nome definitivo do pacote Python e estratégia de distribuição (diretório symlinkado vs. pacote `pip` com entry point) ficam como decisões abertas — ver [09](./09-escopo-e-migracao.md) e [10](./10-roadmap.md).

## Metodologia desta análise

Não foi feita apenas leitura de README. Para responder com segurança à pergunta central, foram lidos:

- Todo o código-fonte Go dos dois binários "escondidos" (não documentados) dentro de `claude-bridge`: `model-router` e `zai-proxy`.
- O histórico de commits de ambos os repositórios (`git log`), que revelou um commit "Backup local project state" contendo artefatos que não deveriam estar versionados.
- O código-fonte real do Hermes Agent (`NousResearch/hermes-agent`, via clone parcial/sparse-checkout): `providers/base.py`, `providers/__init__.py`, `plugins/model-providers/copilot-acp/__init__.py`, `agent/copilot_acp_client.py` e a documentação oficial `website/docs/developer-guide/adding-providers.md`.
- O `--help` completo do CLI `claude` instalado localmente (v2.1.276), para levantar capacidades (streaming real, resume de sessão, modos de permissão) não usadas pela implementação original.

Essa terceira fonte (o próprio Hermes Agent) é o que torna esta análise "profunda": os dois repositórios de terceiros não mencionam a existência do mecanismo `auth_type="external_process"`, porque foi construído para outro provider (Copilot) depois — ou paralelamente — à criação do `claude-bridge`.
