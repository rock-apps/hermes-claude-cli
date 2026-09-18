# hermes-claude-cli

Plugin de provider de modelo para o [Hermes Agent](https://github.com/NousResearch/hermes-agent) que expõe o CLI oficial `claude` (Claude Code), autenticado via assinatura **Claude Max**, como um provider de primeira classe — sem servidor HTTP intermediário.

> **Status**: Fases 1, 3, 4 e 5 implementadas, testadas (81 testes) e validadas de ponta a ponta dentro de um Hermes Agent real (inclusive contra a versão pessoal do mantenedor, pós-`hermes update`). Veja [`docs/10-roadmap.md`](./docs/10-roadmap.md) para o que exatamente foi feito e o que falta, e [`CLAUDE.md`](./CLAUDE.md) para o resumo orientado a quem for continuar o desenvolvimento.

## Por quê

Ferramentas de terceiro que falam a API da Anthropic via chave de API (ou OAuth de terceiro) cobram do "extra usage" da assinatura Claude Max, não da franquia base do plano — o CLI oficial `claude` é o único caminho que usa a franquia base. Este plugin permite que o Hermes Agent use esse caminho, sem servidor HTTP intermediário: fala com o `claude` CLI direto, via subprocesso.

## Instalação

Pré-requisitos: [Claude Code](https://claude.ai/code) instalado e autenticado, e o [Hermes Agent](https://github.com/NousResearch/hermes-agent) instalado.

### Opção 1 — um comando só (recomendado para usar o plugin)

```bash
hermes plugins install rock-apps/hermes-claude-cli/plugin/claude_cli --enable
hermes gateway restart   # se o gateway já estiver rodando
```

Sem clonar nada na mão — o próprio `hermes` clona (só o subdiretório do plugin, não o repositório de análise/docs inteiro), passa pelo scanner de segurança embutido do Hermes e habilita. Depois:

```bash
hermes model   # procure por "Claude CLI (Max subscription)"
```

Atualizar para uma versão nova depois: `hermes plugins update claude-cli-provider`.

### Opção 2 — clone manual (recomendado só para desenvolver este plugin)

```bash
git clone https://github.com/rock-apps/hermes-claude-cli.git
cd hermes-claude-cli
./scripts/install.sh
```

Isso symlinka `plugin/claude_cli/` em `$HERMES_HOME/plugins/model-providers/claude-cli` (default `~/.hermes`), então qualquer edição local no repositório já reflete no Hermes sem reinstalar — é o fluxo usado durante o desenvolvimento deste projeto. Sem build, sem serviço systemd.

Configuração via variáveis de ambiente (todas opcionais) em [`docs/07-configuracao.md`](./docs/07-configuracao.md).

## Documentação

Comece por [`docs/README.md`](./docs/README.md). Destaques:

- [`docs/04-decisao-bridge-e-necessario.md`](./docs/04-decisao-bridge-e-necessario.md) — por que este projeto **não** usa um servidor HTTP (diferente dos projetos que o inspiraram).
- [`docs/05-arquitetura-unificada.md`](./docs/05-arquitetura-unificada.md) — arquitetura proposta.
- [`docs/10-roadmap.md`](./docs/10-roadmap.md) — plano de implementação por fases.

## Projetos de referência analisados

- [`niski84/claude-bridge`](https://github.com/niski84/claude-bridge)
- [`niski84/hermes-claude-cli`](https://github.com/niski84/hermes-claude-cli)
