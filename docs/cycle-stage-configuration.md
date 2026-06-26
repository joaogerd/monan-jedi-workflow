# Etapas cíclicas de MPAS e Obs2IODA

`simpleWorkflow` permanece genérico. Quando um experimento MONAN-JEDI precisa de dados dependentes do horário, ele chama comandos de domínio do `monan-jedi-workflow`.

```text
mpas-prepare CONFIG_DIR --cycle TIME
mpas-submit CONFIG_DIR --cycle TIME
mpas-wait CONFIG_DIR --cycle TIME
mpas-validate CONFIG_DIR --cycle TIME

obs2ioda-doctor CONFIG_DIR --cycle TIME
obs2ioda-prepare CONFIG_DIR --cycle TIME
obs2ioda-run CONFIG_DIR --cycle TIME
obs2ioda-validate CONFIG_DIR --cycle TIME
```

Os comandos usam dois arquivos opcionais no diretório do experimento:

```text
mpas.yaml
obs2ioda.yaml
```

## Contexto de ciclo

Os dois arquivos aceitam os placeholders abaixo:

```text
{cycle_time}       2018-04-15T00:00:00Z
{cycle_id}         20180415T000000Z
{cycle_yyyymmddhh} 2018041500
{cycle_year}       2018
{cycle_month}      04
{cycle_day}        15
{cycle_hour}       00
{mpas_time}        2018-04-15_00:00:00
{valid_time}       instante após lead_hours
{valid_id}         identificador UTC do instante válido
{mpas_valid_time}  instante válido no formato MPAS
{lead_hours}       duração configurada do forecast
{run_dir}          diretório resolvido da etapa MPAS
{work_dir}         diretório resolvido do Obs2IODA
```

## `mpas.yaml`

```yaml
mpas:
  lead_hours: 6
  run_dir: build/mpas/{cycle_id}
  clean_patterns:
    - mpasout.*.nc
    - restart.*.nc

  links:
    - source: /dados/mpas/init/init.{cycle_id}.nc
      target: init.nc
    - source: /dados/mpas/x1.10242.invariant.nc
      target: x1.10242.invariant.nc
    - source: /instalacoes/mpas/bin/mpas_atmosphere
      target: mpas_atmosphere
    - source: /dados/mpas/graphs/x1.10242.graph.info.part.64
      target: x1.10242.graph.info.part.64

  templates:
    - source: templates/mpas/namelist.atmosphere.in
      target: namelist.atmosphere
    - source: templates/mpas/streams.atmosphere.in
      target: streams.atmosphere

  pbs:
    filename: run_mpas.pbs
    job_name: mpas_{cycle_id}
    queue: pesqmini
    select: 1
    ncpus: 64
    mpiprocs: 64
    walltime: "00:30:00"
    launcher: /opt/cray/pals/1.6/bin/mpiexec
    command: [./mpas_atmosphere]
    environment:
      OMP_NUM_THREADS: "1"
      FI_CXI_RX_MATCH_MODE: hybrid

  validation:
    log: stdout.log
    required_log_markers:
      - "MPAS Atmosphere Model"
    required_outputs:
      - mpasout.{mpas_valid_time}.nc
```

`links` adapta a preparação concreta do MPAS: executável, condição inicial, malha, grafo, partição e arquivos de suporte ficam explícitos. Os templates devem conter os placeholders necessários para `config_start_time`, duração, streams `da_state` e arquivos de saída.

## `obs2ioda.yaml` com PREPBUFR

O `obs2ioda_v3` testado no JACI não recebe uma interface genérica de `--input` e `--output`. Ele procura o nome fixo `./prepbufr.bufr` no diretório de trabalho e escreve as coleções IODA nesse mesmo diretório.

O wrapper rastreável `scripts/obs2ioda/run_prepbufr.sh` cria ou verifica esse link e chama o binário sem argumentos:

```yaml
obs2ioda:
  variables:
    workflow_root: /p/projetos/monan_das/USUARIO/projects/monan-jedi-workflow
    obs2ioda_executable: /p/projetos/monan_das/USUARIO/builds/monan-jedi-mpas/bin/obs2ioda_v3
    prepbufr_runner: "{workflow_root}/scripts/obs2ioda/run_prepbufr.sh"

    prepbufr_root: /oper/dados/bdados/assimila/gdas
    prepbufr_input: "{prepbufr_root}/{cycle_year}/{cycle_month}/{cycle_day}/inpe.t{cycle_hour}z.prepbufr.nr"
    output_root: /p/projetos/monan_das/USUARIO/work/obs2ioda-operational

  work_dir: "{output_root}/{cycle_yyyymmddhh}"

  inspection:
    argv: [ncdump, -h, "{output}"]
    required_header_markers: [MetaData, ObsValue, ObsError, PreQC]
    timeout_seconds: 60

  converters:
    - name: prepbufr-surface
      inputs:
        - "{prepbufr_input}"
        - "{prepbufr_runner}"
      outputs:
        - "{work_dir}/sfc_obs_{cycle_yyyymmddhh}.h5"
      timeout_seconds: 900
      argv:
        - bash
        - "{prepbufr_runner}"
        - --executable
        - "{obs2ioda_executable}"
        - --input
        - "{prepbufr_input}"
```

A lista de produtos é parte do contrato de cada caso. O PREPBUFR tutorial de 2018-04-15 produziu seis coleções (`sondes`, `aircraft`, `sfc`, `satwind`, `profiler` e `ascat`); o PREPBUFR operacional testado em 2026-06-26 00 UTC produziu somente `sfc_obs_2026062600.h5`. A ausência de uma coleção não é, por si só, erro do conversor.

Cada conversor mantém logs e manifestos em `<work_dir>/logs/` e `<work_dir>/.monan-jedi-workflow/`. Uma nova execução pula conversores cujos produtos obrigatórios já existam e não estejam vazios; `--force` reexecuta todos os conversores daquele ciclo.

## Uso no `simpleWorkflow`

O template pronto está em:

```text
examples/simpleworkflow/mpas_obs2ioda_cycle/workflow.yaml.example
```

A DAG por ciclo é:

```text
mpas_prepare
  -> mpas_submit ──────────────┐
                                ├-> mpas_wait -> mpas_validate
obs_doctor -> obs_prepare -> obs_run -> obs_validate ┘
```

`mpas_submit` não usa `--wait`: o job PBS é submetido e o processo local continua com Obs2IODA. Quando as observações estiverem validadas, `mpas_wait` acompanha o job MPAS e `mpas_validate` verifica os produtos declarados.

Para um período de pesquisa, o bloco genérico de ciclos é:

```yaml
cycle:
  start: "2018-04-15T00:00:00Z"
  end: "2018-04-30T18:00:00Z"
  step: PT6H
```

O `simpleWorkflow` executa os ciclos sequencialmente e mantém estado e logs distintos por `cycle_id`. Use `--cycle-time`, `--from`, `--to` e `--step` para limitar ou substituir temporariamente o período sem alterar o YAML.

A posição do JEDI deve ser posterior a `mpas_validate` e `obs_validate`, mas a integração cíclica do JEDI ainda requer comandos próprios que recebam `--cycle`. Os comandos estáticos `prepare-runtime`, `render-yaml`, `render-pbs`, `submit --wait` e `validate-run` não devem ser usados como etapa multi-ciclo até essa adaptação.
