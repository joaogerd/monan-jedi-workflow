# Etapas cíclicas de domínio

O `monan-jedi-workflow` expõe stages independentes; `simpleWorkflow` é apenas a orquestração de referência da pesquisa.

## Comandos

### Observações

```text
obs2ioda-doctor   CONFIG_DIR --cycle TIME
obs2ioda-prepare  CONFIG_DIR --cycle TIME
obs2ioda-run      CONFIG_DIR --cycle TIME
obs2ioda-validate CONFIG_DIR --cycle TIME
```

Configuração: `obs2ioda.yaml`.

### Análise MPAS-JEDI

```text
jedi-prepare  CONFIG_DIR --cycle TIME
jedi-submit   CONFIG_DIR --cycle TIME
jedi-wait     CONFIG_DIR --cycle TIME
jedi-validate CONFIG_DIR --cycle TIME
```

Configuração: `jedi.yaml`.

`cycle` representa o horário da análise. O stage resolve separadamente background, janela FGAT, ciclo anterior e próximo ciclo.

### Forecast MPAS

```text
mpas-prepare  CONFIG_DIR --cycle TIME
mpas-submit   CONFIG_DIR --cycle TIME
mpas-wait     CONFIG_DIR --cycle TIME
mpas-validate CONFIG_DIR --cycle TIME
```

Configuração: `mpas.yaml`.

## Workflow de referência

Para simplicidade e portabilidade, o workflow inicial executa um ciclo completo antes de avançar ao próximo:

```text
obs_doctor
  -> obs_prepare
  -> obs_run
  -> obs_validate
  -> jedi_prepare
  -> jedi_submit
  -> jedi_wait
  -> jedi_validate
  -> mpas_prepare
  -> mpas_submit
  -> mpas_wait
  -> mpas_validate
  -> próximo ciclo
```

Essa ordem é propositalmente simples. Paralelismo adicional pode ser introduzido no orquestrador depois que o ciclo mínimo estiver cientificamente validado; os stages não precisam mudar.

O template completo está em:

```text
examples/simpleworkflow/cycled_da/workflow.yaml.example
```

## Estado e manifests

Cada stage mantém seu próprio estado/validação em diretórios de trabalho. O JEDI publica, por exemplo:

```text
RUN/.monan-jedi-workflow/
  jedi-submission.json
  jedi-validation.json
  jedi-artifacts.json
```

O `simpleWorkflow` mantém separadamente o estado da orquestração do workflow. Não confunda estado de orquestração com validação científica do domínio.

## Operação futura

A suite ecFlow deve reproduzir as dependências acima chamando os mesmos comandos `monan-jedi-workflow`. A lógica científica não deve ser portada para scripts ecFlow.
