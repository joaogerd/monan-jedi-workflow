# Etapas cíclicas de MPAS e Obs2IODA

`simpleWorkflow` permanece genérico. Quando um experimento MONAN-JEDI precisa de dados dependentes do horário, ele chama comandos de domínio do `monan-jedi-workflow`.

```text
mpas-prepare CONFIG_DIR --cycle TIME
mpas-submit CONFIG_DIR --cycle TIME --wait
mpas-validate CONFIG_DIR --cycle TIME
obs2ioda-prepare CONFIG_DIR --cycle TIME
obs2ioda-run CONFIG_DIR --cycle TIME
```

Os comandos usam dois arquivos opcionais no diretório do experimento:

```text
mpas.yaml
obs2ioda.yaml
```

Os dois aceitam os placeholders abaixo:

```text
{cycle_time}      2018-04-15T00:00:00Z
{cycle_id}        20180415T000000Z
{mpas_time}       2018-04-15_00:00:00
{valid_time}      instante após lead_hours
{valid_id}        identificador UTC do instante válido
{mpas_valid_time} instante válido no formato MPAS
{lead_hours}      duração configurada do forecast
{run_dir}         diretório resolvido da etapa
{work_dir}        diretório resolvido do Obs2IODA
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

`links` adapta a preparação concreta do MPAS existente no `mpaswf`: executável, condição inicial, malha, grafo, partição e arquivos de suporte ficam explícitos. Os templates devem conter os placeholders necessários para `config_start_time`, duração, streams `da_state` e arquivos de saída.

## `obs2ioda.yaml`

```yaml
obs2ioda:
  work_dir: build/obs2ioda/{cycle_id}
  converters:
    - name: sondes
      inputs:
        - /dados/obs/sondes/{cycle_id}.bufr
      outputs:
        - "{work_dir}/sondes.nc4"
      argv:
        - /instalacoes/obs2ioda/bin/obs2ioda_v3
        - --input
        - /dados/obs/sondes/{cycle_id}.bufr
        - --output
        - "{work_dir}/sondes.nc4"
```

Cada conversor mantém seus próprios logs em `build/obs2ioda/<cycle-id>/logs/`. Uma nova execução pula conversores cujos produtos obrigatórios já existam e não estejam vazios; `--force` reexecuta todos os conversores daquele ciclo.

## Uso no `simpleWorkflow`

A DAG de pesquisa continua curta:

```yaml
cycle:
  start: 2018-04-15T00:00:00Z
  end: 2018-04-30T18:00:00Z
  step: PT6H

tasks:
  - name: prepare_mpas
    argv: [monan-jedi-workflow, mpas-prepare, "{experiment_dir}", --cycle, "{cycle_time}"]

  - name: run_mpas
    depends_on: [prepare_mpas]
    argv: [monan-jedi-workflow, mpas-submit, "{experiment_dir}", --cycle, "{cycle_time}", --wait]

  - name: prepare_obs
    depends_on: [run_mpas]
    argv: [monan-jedi-workflow, obs2ioda-prepare, "{experiment_dir}", --cycle, "{cycle_time}"]

  - name: run_obs
    depends_on: [prepare_obs]
    argv: [monan-jedi-workflow, obs2ioda-run, "{experiment_dir}", --cycle, "{cycle_time}"]
```

A posição relativa dessas tarefas em relação ao 3DVar/FGAT depende do experimento: para assimilação, as observações precisam estar prontas antes de `render-yaml` e `submit --wait`; para geração de ciclos de fundo, o MPAS pode produzir o estado que alimentará o ciclo posterior.
