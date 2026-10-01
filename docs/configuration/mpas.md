# Configuração MONAN/MPAS

O `mpas.yaml` descreve a previsão que parte da análise e produz estados para
o ciclo seguinte. Não comece escrevendo este arquivo do zero: copie o
`examples/case/mpas.yaml` e altere as escolhas marcadas.

## Estrutura

```yaml
mpas:
  variables: ...
  lead_hours: ...
  run_dir: ...
  forecast_contract: ...
  links: ...
  templates: ...
  pbs: ...
  validation: ...
```

## O que cada bloco significa

**variables** — valores reutilizados no arquivo. É onde entram as âncoras
`MONAN_JEDI_INSTALL_ROOT` e `STACK_ROOT` e caminhos científicos do caso.

**lead_hours** — duração total da integração. Deve ser coerente com
`forecast_contract.run_hours`.

**run_dir** — diretório de trabalho de cada ciclo. Normalmente contém
`{cycle_id}`; não use um diretório único para todos os ciclos.

**forecast_contract.da_state_interval_hours** — frequência dos estados MPAS que
podem alimentar a DA/FGAT. Deve dividir `lead_hours`.

**forecast_contract.mpi_ranks** — número de ranks MPI usado pelo modelo.
`pbs.mpiprocs` deve ser coerente com ele.

**forecast_contract.partition** — arquivo de partição correspondente à malha e
ao número de ranks. Não é escolhido pelo workflow.

**links** — arquivos/executáveis que serão ligados ao runtime: análise inicial,
executável MONAN/MPAS, invariant, partição etc.

**templates** — namelist e streams utilizados naquela configuração científica.

**pbs** — recursos do job. Queue, CPUs, ranks e walltime pertencem ao caso/site.

**validation** — define como provar que o forecast terminou corretamente e
quais NetCDF são produtos válidos.

Malha, níveis, timestep, física, partição e recursos não possuem valores
científicos universais no motor. O template documentado mostrará valores de um
caso real apenas quando o baseline 2025 for fechado.
