# Manual do Workflow 3DVar-FGAT MONAN-JEDI

Este documento descreve o fluxo real de execução do caso tutorial `jaci_3dvar_fgat_tutorial_2018041500` no repositório `monan-jedi-workflow`.

O objetivo é deixar explícito quais arquivos são configuração, quais são templates, quais são gerados, quais são copiados ou linkados para o runtime e qual etapa efetivamente executa o `mpasjedi_variational.x`.

Este fluxo em Bash é uma camada temporária e controlada de validação antes da migração completa para Cylc ou ecFlow.

---

## 1. Fluxo geral

```text
configs/sites/jaci/site.env
  ↓
scripts/env/load_jaci_env.sh
  ↓
validadores estruturais e científicos
  ↓
scripts/run/render_3dvar_fgat.sh
  ↓
build/rendered/3dvar_fgat.yaml
  ↓
scripts/run/prepare_3dvar_fgat_runtime.sh --strict
  ↓
build/runtime/jaci_3dvar_fgat_tutorial_2018041500/2018041500
  ↓
scripts/run/render_3dvar_fgat_pbs.sh
  ↓
build/rendered/3dvar_fgat.pbs
  ↓
qsub build/rendered/3dvar_fgat.pbs
  ↓
scripts/run/run_3dvar_fgat_variational.sh --execute
  ↓
mpasjedi_variational.x build/rendered/3dvar_fgat.yaml
```

O script que centraliza o fluxo temporário é:

```bash
scripts/workflows/run_3dvar_fgat_tutorial_2018041500.sh
```

---

## 2. Tabela de etapas

| Step | Script | Inputs | Outputs | Purpose | Notes |
|---|---|---|---|---|---|
| 1 | `scripts/env/load_jaci_env.sh` | `configs/sites/jaci/site.env`, `configs/sites/jaci/modules.sh`, ambiente `spack-stack-inpe` | Variáveis de ambiente, módulos carregados, `MPASJEDI_VARIATIONAL_EXE`, `MPI_LAUNCHER` | Preparar ambiente JACI/MONAN-JEDI | Deve ser consistente com o ambiente usado na compilação. |
| 2 | `tests/smoke_check.sh` | Estrutura do repositório, configs, scripts e ferramentas | Mensagens de validação | Validar estrutura mínima do repositório | Não executa MPAS-JEDI. |
| 3 | `scripts/setup/validate_3dvar_fgat_staged_inputs.sh` | `configs/experiments/3dvar_fgat/data_layout.example.yaml`, `${MONAN_DATA_ROOT}` | Mensagens de arquivos encontrados/faltantes | Verificar se dados esperados estão staged | Verifica background, IODA, covariance, static e graph. |
| 4 | `scripts/setup/validate_3dvar_fgat_file_formats.sh` | Arquivos NetCDF/HDF5/grafos/static | Mensagens de formato | Validar formatos básicos | Não valida ciência completa. |
| 5 | `scripts/setup/validate_3dvar_fgat_mpas_background.sh` | Background MPAS | Mensagens de dimensões e variáveis | Conferir estrutura do background | Útil para detectar campos ausentes. |
| 6 | `scripts/setup/validate_3dvar_fgat_ioda_structure.sh` | Arquivos IODA | Mensagens de grupos IODA | Conferir estrutura mínima das observações | Espera grupos como `MetaData`, `ObsValue`, `ObsError`, `PreQC`. |
| 7 | `scripts/setup/validate_3dvar_fgat_saber_inputs.sh` | `covariance/mpas.stddev.nc`, `covariance/NICAS`, `covariance/VBAL` | Mensagens de validação SABER/BUMP | Conferir insumos do B estático | Prefixos devem casar com os arquivos reais. |
| 8 | `scripts/run/render_3dvar_fgat.sh` | `configs/jedi/applications/3dvar_fgat.yaml`, `configs/experiments/3dvar_fgat/render_context.example.yaml`, `configs/experiments/3dvar_fgat/observers.yaml`, `configs/jedi/obs_plugs/variational/*.yaml` | `build/rendered/observers.yaml`, `build/rendered/render_context.with_observers.yaml`, `build/rendered/3dvar_fgat.yaml`, `build/rendered/provenance/3dvar_fgat.trace` | Renderizar YAML final do JEDI | Não gera PBS e não executa MPAS-JEDI. |
| 9 | `scripts/run/validate_3dvar_fgat_window.sh` | `build/rendered/3dvar_fgat.yaml` | Mensagens de validação temporal | Validar janela FGAT | Confere início, duração e fim inferido. |
| 10 | `scripts/run/validate_3dvar_fgat_jedi_observers.sh` | `build/rendered/3dvar_fgat.yaml`, manifesto de observadores | Mensagens de validação | Conferir observadores renderizados | Evita YAML sem observers esperados. |
| 11 | `scripts/run/prepare_3dvar_fgat_runtime.sh --strict` | `configs/experiments/3dvar_fgat/runtime_manifest.example.yaml`, dados staged, YAML renderizado | `build/runtime/jaci_3dvar_fgat_tutorial_2018041500/2018041500` | Criar diretório runtime e links | Este script não gera PBS. |
| 12 | `scripts/run/run_3dvar_fgat_variational.sh` | `configs/experiments/3dvar_fgat/run_command.example.yaml`, runtime preparado, YAML renderizado | `build/rendered/mpasjedi_variational.command` e, com `--execute`, logs do MPAS-JEDI | Preparar ou executar comando variational | Sem `--execute`, faz dry-run. |
| 13 | `scripts/run/render_3dvar_fgat_pbs.sh` | `configs/experiments/3dvar_fgat/pbs_job.example.yaml`, `jobs/pbs/3dvar_fgat.pbs.template` | `build/rendered/3dvar_fgat.pbs`, `build/rendered/provenance/3dvar_fgat_pbs.trace` | Renderizar script PBS | Não submete o job. |
| 14 | `qsub build/rendered/3dvar_fgat.pbs` | PBS renderizado | Job PBS e logs | Executar no nó computacional | A execução MPI não deve ser feita no login node. |

---

## 3. Artifact provenance

### `build/rendered/3dvar_fgat.yaml`

Gerado por:

```bash
scripts/run/render_3dvar_fgat.sh
```

Entradas principais:

```text
configs/jedi/applications/3dvar_fgat.yaml
configs/experiments/3dvar_fgat/render_context.example.yaml
configs/experiments/3dvar_fgat/observers.yaml
configs/jedi/obs_plugs/variational/*.yaml
```

Produtos intermediários:

```text
build/rendered/observers.yaml
build/rendered/render_context.with_observers.yaml
```

Produto final:

```text
build/rendered/3dvar_fgat.yaml
```

Arquivo de rastreabilidade:

```text
build/rendered/provenance/3dvar_fgat.trace
```

### `build/rendered/observers.yaml`

Gerado por:

```bash
tools/render_observers.py
```

Chamado por:

```bash
scripts/run/render_3dvar_fgat.sh
```

Entradas:

```text
configs/experiments/3dvar_fgat/observers.yaml
configs/jedi/obs_plugs/variational/*.yaml
configs/experiments/3dvar_fgat/render_context.example.yaml
```

### `build/rendered/render_context.with_observers.yaml`

Gerado por:

```bash
scripts/run/render_3dvar_fgat.sh
```

Combina:

```text
configs/experiments/3dvar_fgat/render_context.example.yaml
build/rendered/observers.yaml
```

Esse é o contexto completo usado para renderizar `build/rendered/3dvar_fgat.yaml`.

### `build/rendered/3dvar_fgat.pbs`

Gerado por:

```bash
scripts/run/render_3dvar_fgat_pbs.sh
```

Entradas:

```text
configs/experiments/3dvar_fgat/pbs_job.example.yaml
jobs/pbs/3dvar_fgat.pbs.template
```

Arquivo de rastreabilidade:

```text
build/rendered/provenance/3dvar_fgat_pbs.trace
```

### `build/runtime/jaci_3dvar_fgat_tutorial_2018041500/2018041500`

Gerado por:

```bash
scripts/run/prepare_3dvar_fgat_runtime.sh --strict
```

Entrada:

```text
configs/experiments/3dvar_fgat/runtime_manifest.example.yaml
```

Esse diretório recebe links ou cópias para:

```text
background/
obs/
covariance/
graph/
static/
logs/
analysis/
feedback/
namelist.atmosphere.*
streams.atmosphere.*
stream_list.atmosphere.*
geovars.yaml
keptvars.yaml
obsop_name_map.yaml
```

---

## 4. Arquivos de configuração principais

### Site/JACI

```text
configs/sites/jaci/site.env
configs/sites/jaci/modules.sh
```

Define caminhos, ambiente, stack, executável MPAS-JEDI e launcher MPI.

### Contexto científico/renderização

```text
configs/experiments/3dvar_fgat/render_context.example.yaml
configs/jedi/applications/3dvar_fgat.yaml
```

O primeiro contém valores do caso. O segundo é o template JEDI.

### Observadores

```text
configs/experiments/3dvar_fgat/observers.yaml
configs/jedi/obs_plugs/variational/aircraft.yaml
configs/jedi/obs_plugs/variational/sondes.yaml
configs/jedi/obs_plugs/variational/sfc.yaml
```

### Runtime

```text
configs/experiments/3dvar_fgat/runtime_manifest.example.yaml
```

Declara quais arquivos entram no diretório runtime.

### Comando variational

```text
configs/experiments/3dvar_fgat/run_command.example.yaml
```

Define runtime directory, YAML absoluto, MPI launcher, número de tarefas e variáveis de ambiente.

### PBS

```text
configs/experiments/3dvar_fgat/pbs_job.example.yaml
jobs/pbs/3dvar_fgat.pbs.template
```

Geram `build/rendered/3dvar_fgat.pbs`.

---

## 5. Como executar sem submeter PBS

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env

bash scripts/run/render_3dvar_fgat.sh
bash scripts/run/prepare_3dvar_fgat_runtime.sh --strict
bash scripts/run/render_3dvar_fgat_pbs.sh
bash scripts/run/run_3dvar_fgat_variational.sh
```

Esse fluxo deve gerar:

```text
build/rendered/3dvar_fgat.yaml
build/rendered/observers.yaml
build/rendered/render_context.with_observers.yaml
build/rendered/3dvar_fgat.pbs
build/rendered/mpasjedi_variational.command
build/rendered/provenance/3dvar_fgat.trace
build/rendered/provenance/3dvar_fgat_pbs.trace
```

---

## 6. Como submeter PBS

```bash
bash scripts/run/render_3dvar_fgat.sh
bash scripts/run/prepare_3dvar_fgat_runtime.sh --strict
bash scripts/run/render_3dvar_fgat_pbs.sh
qsub build/rendered/3dvar_fgat.pbs
```

Ou usar o workflow completo:

```bash
bash scripts/workflows/run_3dvar_fgat_tutorial_2018041500.sh --submit
```

---

## 7. Current debugging notes

O caso atual já passou pelas seguintes correções e diagnósticos:

- correção de `state variables` para incluir campos necessários ao MPAS-JEDI;
- ajuste de `geovars.yaml` para `air_pressure_at_surface`;
- alinhamento de `analysis variables`, `control variables` e `state variables` ao vocabulário do tutorial Static-B;
- correção do bloco `BUMP_VerticalBalance` para usar `stream_function`, `velocity_potential`, `temperature` e `surface_pressure`;
- correção dos prefixes NICAS/VBAL para `mpas`, compatível com arquivos `mpas_nicas_local_*`, `mpas_sampling_local_*` e `mpas_vbal_local_*`;
- teste com `MPICH_SMP_SINGLE_COPY_MODE=NONE`;
- teste serial com `io pool size: 1`.

A falha atual ocorre após a leitura das observações `aircraft`, `sondes` e `sfc`, com `signal 11` no rank 0 quando executado em modo serial.

Isso indica que a falha não parece ser causada por MPI, PBS ou decomposição paralela. A investigação deve focar em:

```text
Geometry / streams / static fields / State / GeoVaLs / background error construction
```

Arquivos prioritários para comparar com o tutorial MPAS-JEDI original:

```text
build/rendered/3dvar_fgat.yaml
build/runtime/.../namelist.atmosphere.outer
build/runtime/.../streams.atmosphere.outer
build/runtime/.../geovars.yaml
build/runtime/.../keptvars.yaml
build/runtime/.../obsop_name_map.yaml
data/covariance/mpas.stddev.nc
data/covariance/NICAS/
data/covariance/VBAL/
```

---

## 8. Comandos úteis de inspeção

```bash
ls -l build/rendered/
cat build/rendered/provenance/3dvar_fgat.trace
cat build/rendered/provenance/3dvar_fgat_pbs.trace

grep -n "analysis variables" build/rendered/3dvar_fgat.yaml -A10
grep -n "active variables" build/rendered/3dvar_fgat.yaml -A10
grep -n "linear variable change" build/rendered/3dvar_fgat.yaml -A5
grep -n "files prefix" build/rendered/3dvar_fgat.yaml

find build/runtime/jaci_3dvar_fgat_tutorial_2018041500/2018041500 -maxdepth 2 -type l | sort

tail -n 120 build/runtime/jaci_3dvar_fgat_tutorial_2018041500/2018041500/logs/mpasjedi_variational.log
```
