# Contexto de continuidade — Ciclo de AD MONAN-JEDI

Este documento registra o estado da conversa e da implementação na branch
`feature/cycled-da-roadmap`, para continuidade em outra sessão.

## Objetivo geral

Evoluir o repositório `monan-jedi-workflow` para montar e executar, de modo
progressivo e testável, um ciclo de assimilação de dados com MPAS-JEDI.

A estratégia é:

1. reproduzir primeiro o caso manual já validado;
2. separar a configuração em componentes YAML;
3. manter o YAML principal de experimento mínimo;
4. usar Python somente como motor de composição, validação, planejamento,
   renderização e preparação;
5. evoluir de caso único para dois ciclos, um dia, uma semana, um mês e ciclo
   contínuo.

O repositório principal é `joaogerd/monan-jedi-workflow`. Não criar um novo
repositório para a ciclagem.

## Caso de referência

Baseline validado atualmente:

```text
3D-FGAT
malha x1.10242
análise 2018041500
np64
matriz de covariância de erros de background MPASstatic
observações Radiosonde, GnssroRefNCEP e SfcCorrected
```

O baseline antigo permanece a referência de regressão. A nova arquitetura não
deve remover ou alterar seu comportamento antes de conseguir renderizar um caso
semanticamente equivalente.

## Decisões arquiteturais

### Separação entre Python, YAML e templates

```text
Python = motor do workflow
YAMLs = configuração científica e operacional
Templates = arquivos finais de MPAS, JEDI e PBS
Runtime renderizado = produto, não fonte de verdade
```

Não colocar no código Python:

- detalhes de observações;
- filtros UFO;
- operadores de observação;
- caminhos detalhados de dados;
- parâmetros científicos completos;
- YAML JEDI completo;
- PBS completo;
- namelist ou streams fixos.

### YAML mínimo de experimento

O experimento deve expressar escolhas frequentes:

```yaml
experiment:
  name: cycle_1day_3dfgat_x1.10242

cycle:
  start: 2018-04-15T00:00:00Z
  end: 2018-04-16T00:00:00Z
  interval_hours: 6

assimilation:
  method: 3dvar_fgat
  outer_loops: 2
  inner_iterations: 10
  fgat:
    trajectory_offsets_hours: [-3, 0, 3]

forecast:
  profile: mpas_fgat_3h

background:
  source: previous_forecast

bmatrix:
  name: mpasstatic_x1.10242

observations:
  set: conv_basic

geometry:
  name: x1.10242

run:
  platform: jaci
  tasks: 64
  walltime: '00:30:00'
```

A configuração grossa pertence a componentes separados:

```text
configs/
  assimilation/
  forecast/
  background/
  bmatrix/
  geometry/
  observations/
  platforms/
```

## Modelo FGAT adotado

A discussão corrigiu a hipótese inicial de um único background. Para 3DVar-FGAT,
a assimilação usa uma trajetória de forecast.

Convenção usada no GSI/SMNA para ciclo de 6 h:

```text
janela relativa: [-3 h, 0 h, +3 h]

análise em T
forecast começa em T - 6 h (análise anterior)
forecast termina em T + 3 h
saídas necessárias: T - 3 h, T, T + 3 h
leads: 3 h, 6 h, 9 h
```

Exemplo para análise em 2018-04-15 00Z:

```text
análise anterior: 2018-04-14 18Z
forecast: 18Z -> 03Z

21Z = lead 3 h = offset -3 h
00Z = lead 6 h = offset  0 h
03Z = lead 9 h = offset +3 h
```

O modelo deve permitir futuramente outras janelas, intervalos e origens de
forecast sem modificar o motor Python.

## Regra de testes

Cada passo precisa ser testável antes de avançar.

Ordem obrigatória:

```text
unitário local
-> integração local sem dados reais
-> comparação com baseline
-> preparação no JACI
-> smoke test PBS
-> dois ciclos
-> um dia
-> semana
-> mês
```

Nenhuma etapa cara no JACI deve ser usada para descobrir erros simples de YAML,
datas, dependências, composição ou paths.

## O que já foi criado na branch

### Documentação

```text
docs/roadmap-cycled-da.md
docs/baseline-3dfgat-inventory.md
docs/fgat-trajectory-model.md
docs/testing-strategy-cycled-da.md
docs/cycle-dry-run.md
```

### Planejamento temporal

```text
monan_jedi_workflow/timeline.py
tests/test_timeline.py
```

Implementa:

- parsing UTC;
- IDs de ciclo;
- timestamps MPAS;
- `CycleDefinition`;
- trajetória FGAT configurável;
- `CycleInstance`;
- estados da trajetória com tempo válido, offset e lead.

### Planejador de ciclo

```text
monan_jedi_workflow/cycle_plan.py
scripts/monan-jedi-cycle-plan
tests/test_cycle_plan.py
tests/test_cycle_plan_example.py
```

Uso:

```bash
python scripts/monan-jedi-cycle-plan \
  configs/experiments/cycle_1day_3dfgat_x1.10242.yaml
```

Não cria arquivos nem submete jobs.

### Componentes e composição

```text
monan_jedi_workflow/components.py
monan_jedi_workflow/composition.py

tests/test_components.py
tests/test_committed_component_resolution.py
tests/test_composition.py
```

Implementa:

- resolução por nome dos componentes;
- leitura de YAMLs em `configs/<categoria>/<nome>.yaml`;
- `deep_merge`;
- composição em memória dos defaults dos componentes com overrides mínimos do
  experimento;
- sem alteração no renderer do baseline atual.

### Componentes reais iniciais

```text
configs/assimilation/3dvar_fgat.yaml
configs/forecast/mpas_fgat_3h.yaml
configs/background/previous_forecast.yaml
configs/bmatrix/mpasstatic_x1.10242.yaml
configs/geometry/x1.10242.yaml
configs/platforms/jaci.yaml
configs/observations/conv_basic.yaml
```

### Dry-run

```text
monan_jedi_workflow/dry_run.py
scripts/monan-jedi-cycle-dry-run
tests/test_dry_run.py
```

Uso:

```bash
python scripts/monan-jedi-cycle-dry-run \
  configs/experiments/cycle_1day_3dfgat_x1.10242.yaml
```

O dry-run:

- resolve componentes;
- calcula os quatro ciclos do exemplo de um dia;
- lista trajetórias FGAT;
- lista tarefas planejadas;
- lista artefatos runtime futuros;
- não cria arquivos;
- não submete jobs.

## Arquivo de experimento atual

```text
configs/experiments/cycle_1day_3dfgat_x1.10242.yaml
```

Ele é um exemplo mínimo para planejamento, composição e dry-run. Ainda não é
um caso executável no JACI.

## Testes locais atuais

Executar:

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

Antes de continuar, rodar também a suíte completa:

```bash
python -m pytest
```

## Próximo passo recomendado

Implementar `doctor` como ferramenta somente de leitura.

Objetivo:

```text
validar recursos reais no JACI antes de gerar runtime ou PBS
```

O `doctor` deverá verificar, por configuração declarativa:

- executável `mpasjedi_variational.x`;
- matriz B e metadados;
- arquivo invariante da geometria;
- partição compatível com `run.tasks`;
- arquivos de física;
- arquivos/raízes de observação;
- estados da trajetória previstos para cada ciclo;
- permissões de leitura/escrita nos diretórios necessários.

Comportamento obrigatório:

```text
não criar arquivos
não criar links
não criar diretórios
não renderizar YAML/PBS
não executar MPAS
não executar MPAS-JEDI
não submeter qsub
```

Formato desejado no YAML:

```yaml
doctor:
  checks:
    - name: mpas-jedi executable
      path: /p/projetos/.../mpasjedi_variational.x
      kind: executable

    - name: B matrix
      path: /p/projetos/.../mpasstatic.nc
      kind: file

    - name: MPAS invariant
      path: /p/projetos/.../x1.10242.invariant.nc
      kind: file

    - name: physics directory
      path: /p/projetos/.../physics
      kind: directory
```

Testes obrigatórios para o `doctor`:

1. arquivo existente;
2. arquivo ausente;
3. diretório existente;
4. executável presente/ausente;
5. placeholders temporais por ciclo, quando implementados;
6. YAML inválido;
7. garantia de que nada foi modificado no filesystem;
8. integração local com diretório temporário;
9. só depois teste no JACI com paths reais.

## Limitação encontrada

Na sessão anterior, tentativas de criar o módulo `doctor` pela integração de
GitHub foram bloqueadas antes de gerar commit. Portanto, **o doctor ainda não
existe na branch**.

Não assumir que ele foi implementado.

## Commits relevantes da branch

```text
b522218 docs: add cycled data assimilation roadmap
22a8f29 docs: inventory baseline configuration for component migration
4b519ab feat: add pure cycle timeline resolver
fea346b test: cover cycle timeline resolution
df4967 feat: model FGAT trajectories instead of one background time
3defe8 test: verify GSI-style FGAT trajectory planning
2066aba docs: define configurable FGAT trajectory model
cea2c54 docs: define incremental testing strategy for cycled DA
873e8f1 feat: add side-effect-free cycle planning
5ae0c49 test: cover side-effect-free cycle planning
b07a041 feat: add standalone cycle planning command
6ec9681 feat: add minimal one-day FGAT plan configuration
f5402d5 test: validate committed one-day cycle plan example
cf5eb07 feat: add declarative component repository resolver
0748246 test: cover named component resolution
f7759d1 feat: add 3DVar-FGAT method component
739dd37 feat: add three-hour MPAS FGAT forecast profile
f351531 feat: add previous forecast background component
36b7b12 feat: add MPASstatic B matrix component
b0fb9bf feat: add x1 geometry component
83df075 feat: add JACI platform component
5f4e8af feat: add conventional observation set component
0e44eb9 test: resolve all components for committed cycle example
8151e1e feat: compose effective cyclic experiment configuration
7892ea0 test: verify effective cyclic experiment composition
bad6bb4 feat: add side-effect-free cyclic dry run
47f486c feat: add standalone cyclic dry run command
53fbe27 test: cover side-effect-free cyclic dry run
d271595 docs: describe cyclic dry run workflow check
```

## Prompt para retomar em nova conversa

```text
Continue o trabalho no repositório joaogerd/monan-jedi-workflow, branch
feature/cycled-da-roadmap.

Leia primeiro docs/conversation-handoff-cycled-da.md e siga as decisões e o
estado registrados nele.

A próxima tarefa é implementar o comando/ferramenta doctor, somente de leitura,
com testes locais completos antes de qualquer validação no JACI. Não alterar o
renderer do baseline nem criar/submeter jobs. Cada mudança deve ter testes
executáveis e critério de aceite.
```
