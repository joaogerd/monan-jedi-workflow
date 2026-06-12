# Tutorial do baseline 3D-FGAT MPASstatic x1.10242

Este tutorial descreve como reproduzir e interpretar o baseline validado:

```text
3dfgat_mpastatic_x1.10242_2018041500
```

O objetivo é registrar, de forma prática, o que já foi validado no JACI, quais comandos devem ser executados, quais arquivos são gerados e como confirmar que a execução terminou corretamente.

## 1. O que este baseline representa

Este baseline é um caso mínimo validado do MPAS-JEDI usando:

| Campo | Valor |
|---|---|
| Método | 3D-FGAT |
| Covariância | MPASstatic |
| Malha | x1.10242 |
| Ciclo | 2018041500 |
| Data de análise | 2018-04-15 00 UTC |
| Background | 2018-04-14 21 UTC |
| Janela | 6 horas |
| MPI | 64 ranks |
| Minimizador | DRPCG |
| Iterações internas | 10 |

A configuração principal está em:

```text
configs/experiments/3dfgat_mpastatic_x1.10242_2018041500/
```

O arquivo `experiment.yaml` define o nome do experimento, ciclo, malha, número de ranks MPI, método, covariância, minimizador e caminhos principais.

## 2. Arquivos de configuração do baseline

O baseline é composto, principalmente, por três arquivos:

```text
configs/experiments/3dfgat_mpastatic_x1.10242_2018041500/experiment.yaml
configs/experiments/3dfgat_mpastatic_x1.10242_2018041500/runtime.yaml
configs/experiments/3dfgat_mpastatic_x1.10242_2018041500/validation.yaml
```

### `experiment.yaml`

Define o contrato científico e computacional do experimento:

```yaml
experiment:
  name: 3dfgat_mpastatic_x1.10242_2018041500
  stage: baseline
cycle:
  id: '2018041500'
  analysis_datetime: '2018-04-15T00:00:00Z'
  background_datetime: '2018-04-14T21:00:00Z'
  window_begin: '2018-04-14T21:00:00Z'
  window_length: PT6H
geometry:
  mesh: x1.10242
  np: 64
method:
  cost_type: 3D-FGAT
  covariance_model: MPASstatic
  minimizer: DRPCG
  ninner: 10
```

Também define o executável esperado:

```text
/p/projetos/monan_das/${USER}/builds/monan-jedi-mpas/bin/mpasjedi_variational.x
```

### `runtime.yaml`

Define os links simbólicos, diretórios e arquivos físicos necessários para montar o diretório de execução do MPAS-JEDI.

Entre os itens importantes estão:

```text
background/mpasout.2018-04-14_21.00.00.nc
x1.10242.invariant.nc
x1.10242.graph.info.part.64
namelist.atmosphere.outer
namelist.atmosphere.inner
streams.atmosphere.outer
streams.atmosphere.inner
geovars.yaml
keptvars.yaml
Data/ufo/testinput_tier_1
```

Também há uma verificação explícita dos tempos `xtime` esperados:

```text
background/mpasout.2018-04-14_21.00.00.nc: 2018-04-14_21:00:00
templateFields.10242.nc: 2018-04-15_00:00:00
```

### `validation.yaml`

Define o que precisa ser validado antes de executar o baseline:

```yaml
validation:
  profile: strict_baseline
  expected:
    experiment_name: 3dfgat_mpastatic_x1.10242_2018041500
    cost_type: 3D-FGAT
    covariance_model: MPASstatic
    mesh: x1.10242
    np: 64
    mpiprocs: 64
```

Também registra os observadores esperados:

```text
Radiosonde
GnssroRefNCEP
SfcCorrected
```

E os diretórios obrigatórios do runtime:

```text
background
Data/os
Data/states
testinput
```

## 3. Ordem correta de execução

A ordem correta para preparar e executar o baseline é:

```bash
python3 -m py_compile monan_jedi_workflow/*.py

python3 -m monan_jedi_workflow.cli validate-config \
  configs/experiments/3dfgat_mpastatic_x1.10242_2018041500

python3 -m monan_jedi_workflow.cli prepare-runtime \
  configs/experiments/3dfgat_mpastatic_x1.10242_2018041500

python3 -m monan_jedi_workflow.cli render-yaml \
  configs/experiments/3dfgat_mpastatic_x1.10242_2018041500

python3 -m monan_jedi_workflow.cli render-pbs \
  configs/experiments/3dfgat_mpastatic_x1.10242_2018041500

qsub build/rendered/3dfgat_mpastatic_x1.10242_2018041500.pbs
```

Essa ordem não deve ser invertida. A validação deve ocorrer antes da preparação do runtime, e o YAML/PBS devem ser renderizados depois do runtime estar corretamente preparado.

## 4. Checagens seguras antes da execução real

Antes de executar no PBS, as checagens seguras recomendadas são:

```bash
make install
make test
make validate
make render-yaml
make render-pbs
```

Esses comandos instalam o pacote, executam testes, validam a configuração e renderizam os arquivos finais. Eles não submetem job e não executam o `mpasjedi_variational.x`.

## 5. Política de execução real

A execução real deve permanecer manual e explícita.

O repositório não deve chamar automaticamente:

```text
qsub
mpiexec
mpirun
mpasjedi_variational.x
```

O PBS renderizado pode conter o comando MPI, mas a submissão do job deve ser feita manualmente pelo usuário.

## 6. Arquivos renderizados esperados

Após `render-yaml` e `render-pbs`, os arquivos esperados são:

```text
build/rendered/3dfgat_mpastatic_x1.10242_2018041500.yaml
build/rendered/3dfgat_mpastatic_x1.10242_2018041500.pbs
```

Na execução validada no JACI, os caminhos completos foram:

```text
rendered_yaml: /p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow_v2/build/rendered/3dfgat_mpastatic_x1.10242_2018041500.yaml
rendered_pbs:  /p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow_v2/build/rendered/3dfgat_mpastatic_x1.10242_2018041500.pbs
```

## 7. Execução validada no JACI

O baseline foi validado com sucesso no JACI com o seguinte registro:

| Campo | Valor |
|---|---|
| Data | 2026-06-10 |
| Job ID | 264572.pbs-ha |
| Login node | ian05 |
| MPI ranks | 64 |
| Resultado | success |

Diretório de trabalho usado na execução:

```text
/p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow_v2/build/rendered
```

Diretório runtime usado:

```text
/p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow_v2/build/runtime/3dfgat_mpastatic_x1.10242_2018041500/2018041500
```

Arquivo de log registrado:

```text
/p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow_v2/build/runtime/3dfgat_mpastatic_x1.10242_2018041500/2018041500/logs/run_3dfgat_workflow_geometry_background_np64.264572.pbs-ha.log
```

## 8. Como confirmar sucesso

A execução validada terminou com:

```text
Run: Finishing oops::Variational<MPAS, UFO and IODA observations> with status = 0
```

Em outro documento do workflow, o sucesso esperado também é descrito como:

```text
Run: Finishing oops::Variational with status = 0
OOPS Ending
```

Portanto, para confirmar que a execução terminou corretamente, procure no log por:

```bash
grep -E "Finishing oops::Variational|OOPS Ending|status = 0" \
  build/runtime/3dfgat_mpastatic_x1.10242_2018041500/2018041500/logs/*.log
```

A confirmação mais forte é a presença de `status = 0` na finalização do `oops::Variational`.

## 9. Resultados gerados pelo baseline

A execução bem-sucedida gerou os seguintes arquivos de análise e saída em espaço de observação:

```text
Data/states/mpas.3dfgat.2018-04-15_00.00.00.nc
Data/os/obsout_3dfgat_sondes.nc4
Data/os/obsout_3dfgat_sfc.nc4
Data/os/obsout_3dfgat_gnssroref.nc4
```

Os tamanhos observados foram:

```text
Data/states/mpas.3dfgat.2018-04-15_00.00.00.nc: 31M
Data/os/obsout_3dfgat_sondes.nc4: 734K
Data/os/obsout_3dfgat_sfc.nc4: 381K
Data/os/obsout_3dfgat_gnssroref.nc4: 97K
```

Esses arquivos são os principais produtos do baseline:

| Arquivo | Interpretação |
|---|---|
| `Data/states/mpas.3dfgat.2018-04-15_00.00.00.nc` | estado/análise MPAS gerado pelo 3D-FGAT |
| `Data/os/obsout_3dfgat_sondes.nc4` | saída de observações para sondagens |
| `Data/os/obsout_3dfgat_sfc.nc4` | saída de observações de superfície corrigidas |
| `Data/os/obsout_3dfgat_gnssroref.nc4` | saída de observações GNSS-RO refratividade |

## 10. Verificações pós-execução

Depois que o job terminar, entre no runtime:

```bash
cd build/runtime/3dfgat_mpastatic_x1.10242_2018041500/2018041500
```

Verifique se os arquivos principais existem:

```bash
ls -lh \
  Data/states/mpas.3dfgat.2018-04-15_00.00.00.nc \
  Data/os/obsout_3dfgat_sondes.nc4 \
  Data/os/obsout_3dfgat_sfc.nc4 \
  Data/os/obsout_3dfgat_gnssroref.nc4
```

O resultado esperado, com base na execução validada, é aproximadamente:

```text
31M  Data/states/mpas.3dfgat.2018-04-15_00.00.00.nc
734K Data/os/obsout_3dfgat_sondes.nc4
381K Data/os/obsout_3dfgat_sfc.nc4
97K  Data/os/obsout_3dfgat_gnssroref.nc4
```

Os tamanhos podem variar levemente conforme sistema de arquivos, mas os arquivos devem existir e não devem estar vazios.

## 11. Limpeza antes de reexecutar

Antes de reexecutar o MPAS-JEDI no mesmo runtime, remova as saídas anteriores:

```bash
rm -rf Data/os Data/states
mkdir -p Data/os Data/states
```

Isso evita erro caso o MPAS-JEDI tente escrever arquivos que já existem.

## 12. O que registrar em novas validações

Para manter o baseline auditável, novas validações devem registrar:

```text
commit
tag
job_id
login_node
runtime_dir
rendered_yaml
rendered_pbs
log_file
output_files
result
```

Esse registro permite comparar execuções quando o workflow evoluir, novos ciclos forem adicionados, novas observações forem incluídas ou diferentes opções de covariância forem testadas.

## 13. Resumo operacional

O fluxo mínimo para reproduzir o baseline é:

```bash
make install
make test
make validate
make render-yaml
make render-pbs
qsub build/rendered/3dfgat_mpastatic_x1.10242_2018041500.pbs
```

O resultado esperado é:

```text
Run: Finishing oops::Variational<MPAS, UFO and IODA observations> with status = 0
```

E os principais produtos esperados são:

```text
Data/states/mpas.3dfgat.2018-04-15_00.00.00.nc
Data/os/obsout_3dfgat_sondes.nc4
Data/os/obsout_3dfgat_sfc.nc4
Data/os/obsout_3dfgat_gnssroref.nc4
```
