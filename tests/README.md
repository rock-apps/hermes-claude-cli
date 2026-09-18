# Testes

54 testes, todos passando (`pytest -q` → `54 passed`). Nenhum invoca o `claude` CLI real — subprocessos são simulados com um binário fake em `test_process.py`, e `test_client.py`/`test_config.py` usam `monkeypatch`. Isso mantém a suíte rápida (~0.3s) e sem custo de uso real da assinatura.

| Arquivo | Cobre |
|---|---|
| `test_protocol.py` | achatamento de mensagens, normalização de alias de modelo, mapeamento de `stop_reason` (23 testes) |
| `test_process.py` | construção de argv (`build_args`) e spawn/parse do subprocesso (`run_once`), incluindo o caminho de erro real do CLI e timeout (14 testes) |
| `test_config.py` | resolução de variáveis de ambiente e defaults (9 testes) |
| `test_client.py` | orquestração do `ClaudeCLIClient` (normalização de modelo, wiring de permissões, forma da resposta) com `run_once` mockado (8 testes) |
| `test_plugin_init.py` | `plugin/claude_cli/__init__.py` não quebra quando importado fora de um processo Hermes real (1 teste) |

Rodar tudo:
```
cd /mnt/dev/projects-rk/hermes-claude-cli
.venv/bin/python -m pytest -q
```

Um smoke test manual real (não automatizado — para não gastar uso da assinatura a cada execução da suíte) está documentado em `../docs/10-roadmap.md`, seção "Fase 1".
