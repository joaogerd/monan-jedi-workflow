# Ciclagem MPAS + Obs2IODA com simpleWorkflow

Este é o template de orquestração para o estágio anterior à assimilação: gerar o background com MPAS e converter PREPBUFR em IODA para os mesmos ciclos. A matriz B é uma entrada externa, já construída e validada; ela não faz parte desta DAG.

## Pré-requisitos

1. `simpleWorkflow` com suporte a `cycle` instalado no ambiente Python usado no JACI.
2. `monan-jedi-workflow` instalado e disponível no `PATH`.
3. Um diretório de caso contendo `mpas.yaml` e `obs2ioda.yaml` compatíveis com a mesma malha, ciclo e convenção de caminhos.
4. Ambiente JACI carregado antes da execução. O executável `obs2ioda_v3` depende das bibliotecas do stack, incluindo `libfabric`.

```bash
source /p/projetos/monan_das/${USER}/projects/monan-jedi-workflow/scripts/load_jaci_env.sh
```

## Preparar um caso local

Copie o template para o diretório do caso e substitua `USUARIO` e o período de ciclos:

```bash
mkdir -p cases/mpas_obs2ioda_x1.10242
cp examples/simpleworkflow/mpas_obs2ioda_cycle/workflow.yaml.example \
  cases/mpas_obs2ioda_x1.10242/simpleworkflow.yaml

${EDITOR:-vi} cases/mpas_obs2ioda_x1.10242/simpleworkflow.yaml
```

O valor de `experiment_dir` deve apontar para o próprio diretório do caso. Nesse diretório devem existir:

```text
mpas.yaml
obs2ioda.yaml
simpleworkflow.yaml
```

## Ordem de execução por ciclo

```text
mpas_prepare
  -> mpas_submit ──────────────┐
                                ├-> mpas_wait -> mpas_validate
obs_doctor -> obs_prepare -> obs_run -> obs_validate ┘
```

`mpas_submit` registra o Job ID PBS e retorna sem esperar. Enquanto o job aguarda ou executa nos nós de computação, o processo local prepara, converte e valida as observações. Depois de `obs_validate`, `mpas_wait` acompanha a conclusão do MPAS e `mpas_validate` confirma os produtos declarados no caso.

A DAG do `simpleWorkflow` permanece sequencial no nó de login; a sobreposição ocorre porque o MPAS já foi submetido ao PBS antes de iniciar Obs2IODA.

## Executar e retomar

```bash
simpleworkflow plan cases/mpas_obs2ioda_x1.10242/simpleworkflow.yaml

simpleworkflow run cases/mpas_obs2ioda_x1.10242/simpleworkflow.yaml \
  --workdir work/simpleworkflow/mpas_obs2ioda_x1.10242
```

Para testar apenas um ciclo:

```bash
simpleworkflow run cases/mpas_obs2ioda_x1.10242/simpleworkflow.yaml \
  --cycle-time 2026-06-26T00:00:00Z \
  --workdir work/simpleworkflow/mpas_obs2ioda_x1.10242
```

Para alterar temporariamente um intervalo sem editar o YAML:

```bash
simpleworkflow run cases/mpas_obs2ioda_x1.10242/simpleworkflow.yaml \
  --from 2026-06-26T00:00:00Z \
  --to 2026-06-26T12:00:00Z \
  --step PT6H \
  --workdir work/simpleworkflow/mpas_obs2ioda_x1.10242
```

O estado, logs e registros de tentativas são separados por `cycle_id`; portanto, uma retomada não confunde `00Z`, `06Z` e `12Z`.

## Limite atual

Este template termina em `mpas_validate`. A etapa seguinte será adicionar comandos cíclicos de preparação, submissão e validação do JEDI que consumam, para o mesmo ciclo, o manifesto MPAS, o manifesto Obs2IODA e a matriz B declarada pelo caso. Não use os comandos estáticos `prepare-runtime` e `submit --wait` para vários ciclos, pois eles ainda não recebem `--cycle`.
