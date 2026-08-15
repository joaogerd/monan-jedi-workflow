# ADR 0002 — simpleWorkflow como orquestrador de referência de pesquisa

**Status:** accepted

## Contexto

Shell puro é simples, mas rapidamente acumula lógica de dependências, estado, restart e logs. ecFlow resolve problemas maiores que o necessário para uma campanha científica local e pertence à infraestrutura operacional.

## Decisão

`simpleWorkflow` será usado como orquestrador de referência nos experimentos de pesquisa MONAN-JEDI.

Ele não será importado pelo pacote `monan_jedi_workflow` nem será requisito para chamar os stages diretamente.

## Consequências

- a pesquisa ganha DAG, ciclos, restart e proveniência;
- o workflow continua inspecionável e pequeno;
- exemplos `workflow.yaml` funcionam como especificação executável da DAG;
- a futura tradução para ecFlow/Cylc atua somente na camada de orquestração.
