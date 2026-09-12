# Status e restart

## Ver o estado da campanha

```bash
swf status CASE/workflow.yaml
```

O `simpleWorkflow` mantém estado e logs por tentativa. Uma tarefa concluída pode ser reutilizada quando sua assinatura e seus outputs continuam válidos.

## Depurar uma etapa sem o orquestrador

Todos os stages permanecem chamáveis diretamente. Exemplo para JEDI:

```bash
monan-jedi-workflow jedi-prepare CASE --cycle TIME
monan-jedi-workflow jedi-submit  CASE --cycle TIME
monan-jedi-workflow jedi-wait    CASE --cycle TIME
monan-jedi-workflow jedi-validate CASE --cycle TIME
```

Isso é útil quando uma campanha para em uma etapa específica.

## PBS terminou, mas o workflow falhou

Isso pode ser correto. `wait` responde somente à pergunta “o job saiu do scheduler?”. `validate` verifica logs e produtos esperados.

Procure primeiro:

- log declarado pelo stage;
- `*.json` em `.monan-jedi-workflow/` do runtime;
- outputs obrigatórios do stage.

## Reexecutar

Evite apagar diretórios de estado sem entender a falha. Corrija a entrada/configuração e use os mecanismos de restart/reset do `simpleWorkflow` para a tarefa necessária.

Para uma submissão JEDI já registrada, `jedi-submit` reutiliza o Job ID por padrão. Um novo envio requer `--resubmit` explicitamente.

## Mudança de runtime skeleton

Não reutilize o mesmo `run_dir` com um skeleton científico diferente. O stage JEDI bloqueia essa situação para evitar mistura silenciosa de streams/tabelas/assets incompatíveis.
