# Dry-run do ciclo de assimilação

## Objetivo

O dry-run resolve um experimento cíclico sem criar diretórios, links, YAMLs
renderizados, scripts PBS ou jobs. Ele é o primeiro teste obrigatório antes de
qualquer etapa de preparação no JACI.

## Comando

```bash
python scripts/monan-jedi-cycle-dry-run \
  configs/experiments/cycle_1day_3dfgat_x1.10242.yaml
```

## O que o comando verifica

- o experimento seleciona componentes existentes;
- método, forecast, background, matriz B, geometria, observações e plataforma
  são resolvidos;
- a trajetória FGAT é calculada para todos os ciclos;
- os estados necessários, leads e duração de forecast são coerentes;
- as tarefas futuras são listadas em ordem;
- os artefatos runtime esperados são mostrados por ciclo.

## O que o comando não faz

```text
não cria arquivos
não cria links
não cria diretórios runtime
não lê NetCDF
não verifica paths reais do JACI
não renderiza YAML JEDI ou PBS
não executa MPAS
não executa MPAS-JEDI
não chama qsub
```

## Exemplo resumido

```text
[OK] components resolved
  assimilation: 3dvar_fgat
  forecast: mpas_fgat_3h
  background: previous_forecast
  bmatrix: mpasstatic_x1.10242

[PLAN] cycle 2018041500
  trajectory forecast: 2018-04-14T18:00:00Z -> 2018-04-15T03:00:00Z
  required trajectory states:
    - 2018-04-14T21:00:00Z offset=-3h lead=3h
    - 2018-04-15T00:00:00Z offset=0h lead=6h
    - 2018-04-15T03:00:00Z offset=3h lead=9h
```

## Critério de aceite

Antes de implementar `prepare`, o dry-run do experimento de um dia deve:

1. listar exatamente quatro ciclos: 00Z, 06Z, 12Z e 18Z;
2. usar a trajetória 18Z→03Z para análise em 00Z;
3. usar a trajetória 00Z→09Z para análise em 06Z;
4. resolver todos os componentes selecionados;
5. terminar sem criar ou modificar arquivos.

## Testes locais

```bash
python -m pytest \
  tests/test_timeline.py \
  tests/test_cycle_plan.py \
  tests/test_cycle_plan_example.py \
  tests/test_components.py \
  tests/test_committed_component_resolution.py \
  tests/test_composition.py \
  tests/test_dry_run.py
```
