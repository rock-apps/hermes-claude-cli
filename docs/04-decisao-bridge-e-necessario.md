# 04 — ADR: o `claude-bridge` é necessário?

**Status**: aceito (decisão de arquitetura para este projeto).

## Contexto

O usuário pediu explicitamente: *"de repente esse bridge não é preciso. ou é. analise."* Esta é a pergunta que orienta toda a arquitetura proposta em [05](./05-arquitetura-unificada.md).

## Pergunta desmembrada em duas partes

### Parte 1 — A *função* do bridge é necessária?

**Sim.** O `claude` CLI não expõe nenhuma API HTTP; ele é invocado via linha de comando com stdin/stdout/argv. O Hermes Agent, por outro lado, modela **todo** provider de modelo como algo que fala um `api_mode` de rede (`chat_completions`, `anthropic_messages` ou `codex_responses`) — ver [03](./03-modelo-de-provider-do-hermes.md). Não existe, no Hermes, um "provider genérico sem protocolo" — mesmo o caso mais próximo disso (`copilot-acp`) ainda se anuncia como `api_mode="chat_completions"` e implementa uma classe de cliente que expõe a interface `.chat.completions.create()`.

Conclusão: **alguma camada de tradução entre "chamada de provider do Hermes" e "invocação do CLI `claude`" é obrigatória.** Não há como eliminar essa responsabilidade.

### Parte 2 — A *implementação atual* (servidor HTTP Go, repositório separado, systemd) é necessária?

**Não.** Ela é uma escolha de implementação, não um requisito do Hermes. O Hermes já expõe um mecanismo de extensão de primeira classe, testado em produção pela própria Nous Research, desenhado exatamente para "provider cujo protocolo não é HTTP":

```python
class ProviderProfile:
    auth_type: str = "api_key"  # ... ou "external_process"
    def create_client(self, **client_kwargs) -> Any | None:
        """Retorna um cliente customizado. None = usa o cliente OpenAI HTTP padrão."""
```

Isso é usado hoje pelo provider bundled `copilot-acp`, que fala com o binário `copilot` via subprocesso + stdio (protocolo ACP/JSON-RPC), **sem nenhum servidor HTTP, porta ou processo systemd**.

## Decisão

A arquitetura unificada **não terá um servidor HTTP separado**. Em vez disso:

1. O plugin registra um `ProviderProfile` com `auth_type="external_process"` (mesmo padrão do `copilot-acp`).
2. `create_client()` devolve uma classe própria, ex. `ClaudeCLIClient`, que expõe `.chat.completions.create(...)`.
3. Internamente, `ClaudeCLIClient` invoca `claude -p --output-format stream-json ...` como subprocesso **dentro do próprio processo Python do Hermes** — sem socket, sem porta, sem processo daemon separado.
4. A tradução de mensagens OpenAI ⇄ prompt/flags do `claude` CLI (o que hoje vive em `main.go` do `claude-bridge`) migra para um módulo Python dentro deste mesmo plugin.

## Consequências

### Positivas

- **Elimina a superfície de ataque de rede inteira.** Não existe mais "porta 9180 sem autenticação escutando em `0.0.0.0`" (risco real identificado em [01](./01-analise-claude-bridge.md)) — porque não existe porta nenhuma.
- **Um repositório, uma linguagem.** Não há mais Go + Python + 2 repositórios git + clone em tempo de instalação + toolchain extra. Todo o plugin é Python, no mesmo processo que o Hermes já roda.
- **Sem processo systemd adicional para manter vivo, reiniciar, ou monitorar.** O subprocesso `claude` vive e morre com cada chamada (ou com a sessão, se optarmos por reuso — ver [05](./05-arquitetura-unificada.md)), gerenciado pelo próprio ciclo de vida do Hermes.
- **Acesso a funcionalidades do CLI que o bridge HTTP não usava**: streaming real (`stream-json` + `--include-partial-messages`), resume de sessão (`--session-id`/`--resume`), modos de permissão mais granulares que "bypass total" (ver [06](./06-referencia-cli-claude.md) e [08](./08-seguranca.md)).
- **Instalação mais simples**: sem `go build`, sem clonar um segundo repositório, sem editar unit systemd.

### Negativas / trade-offs a monitorar

- Perdemos a possibilidade de expor o "bridge" para **outras ferramentas fora do Hermes** (o README do `claude-bridge` cita Open WebUI, LibreChat, Cursor como consumidores adicionais do endpoint HTTP). Se a Rock Apps também quiser essa reutilização multi-cliente, um modo HTTP "opcional" pode ser mantido como funcionalidade **separada e explicitamente opt-in** (ver alternativa abaixo), não como padrão do plugin do Hermes.
- O subprocesso ainda tem overhead de inicialização (~1–3s por chamada), igual ao bridge original — isso é uma limitação do `claude` CLI em si, não do transporte.
- Dependemos de uma API interna do Hermes (`ProviderProfile.create_client`, `auth_type="external_process"`) que, embora documentada e usada em produção, pode mudar entre versões do Hermes Agent — precisa de teste de compatibilidade ao atualizar a dependência (ver [10](./10-roadmap.md)).

## Alternativa considerada e rejeitada (para v1)

**Manter um servidor HTTP, mas embutido no mesmo processo/pacote** (ex.: um `http.server` Python rodando em thread, iniciado por um hook de lifecycle do plugin) em vez de subprocesso puro. Rejeitada para v1 porque:

- Hermes não oferece um hook de "on plugin load, start background service" documentado — teríamos que inferir/hackear esse comportamento.
- Ainda herdaria o problema de "porta local sem necessidade" mesmo que resolvesse "dois repositórios".
- O padrão `external_process` é estritamente melhor quando o único consumidor é o Hermes.

Fica registrada como opção de **modo dual** futuro (flag de configuração `CLAUDE_CLI_TRANSPORT=subprocess|http`) caso apareça um requisito real de reuso fora do Hermes — ver [10](./10-roadmap.md).
