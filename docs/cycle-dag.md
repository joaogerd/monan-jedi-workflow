# DAG cíclico declarativo

`monan_jedi_workflow.cycle_dag` transforma os ciclos resolvidos pelo planejador
em uma lista determinística de tarefas e dependências.

A camada é estritamente declarativa:

- não cria diretórios;
- não renderiza YAML, namelist, streams ou PBS;
- não executa MPAS, MPAS-JEDI ou conversores;
- não consulta scheduler;
- não lê dados científicos.

## Estágios centrais por ciclo

Cada ciclo recebe, nesta ordem:

```text
prepare
observations
background
assimilate
forecast
```

O primeiro `background` é marcado como dependente de entrada externa. Nos ciclos
seguintes, `background.<cycle>` depende de `forecast.<previous_cycle>`.

Exemplo:

```text
background.2018041500 depends_on=prepare.2018041500 external_input=true
background.2018041506 depends_on=prepare.2018041506, forecast.2018041500
```

## Diagnósticos opcionais

Quando `include_diagnostics=True`, duas tarefas laterais são adicionadas:

```text
diagnostics_analysis.<cycle>  depends_on=assimilate.<cycle>
diagnostics_forecast.<cycle>  depends_on=forecast.<cycle>
```

Essas tarefas não atrasam o próximo ciclo. A decisão operacional de bloquear ou
não bloquear o ciclo com base em diagnósticos será uma política posterior do
orquestrador.

## Papel no workflow completo

O MONAN-JEDI produzirá esse DAG e um orquestrador, como `simpleWorkflow`, Cylc ou
ecFlow, será responsável por executar cada tarefa. A ciência e a composição dos
arquivos continuam no `monan-jedi-workflow`; o orquestrador apenas respeita as
dependências.
