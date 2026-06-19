# Contexto de continuidade — Ciclo de AD MONAN-JEDI

Este documento registra o estado atual da implementação na branch
`feature/cycled-da-roadmap`.

## Objetivo geral

Evoluir `joaogerd/monan-jedi-workflow` para montar e executar, de modo
progressivo e testável, um ciclo de assimilação de dados com MPAS-JEDI.

A ordem obrigatória permanece:

```text
planejamento/local puro
-> integração local sem dados reais
-> comparação com baseline
-> preparação no JACI
-> smoke PBS
-> dois ciclos
-> um dia, semana, mês e operação contínua
```

Nenhuma etapa cara no JACI deve ser usada para identificar erro de YAML, datas,
composição, paths, dependências ou templates.

## Caso de referência

O baseline manual validado permanece:

```text
3D-FGAT
malha x1.10242
análise 2018041500
np64
matriz de covariância de erros de background MPASstatic
observações Radiosonde, GnssroRefNCEP e SfcCorrected
```

O baseline antigo é referência de regressão. A nova arquitetura não deve
remover ou alterar seu comportamento antes de renderizar um caso
semanticamente equivalente.

## Decisões arquiteturais que continuam válidas

```text
Python = motor do workflow
YAMLs = configuração científica e operacional
Templates = arquivos finais MPAS, JEDI e PBS
Runtime renderizado = produto, não fonte de verdade
```

O YAML mínimo seleciona método, perfil de forecast, estratégia de background,
matriz B, observações, geometria e plataforma. Detalhes científicos, filtros
UFO, caminhos de dados e templates completos não devem ser codificados no
motor Python.

A convenção FGAT de referência é:

```text
janela relativa: [-3 h, 0 h, +3 h]
análise em T
forecast inicia em T - 6 h
saídas necessárias: T - 3 h, T, T + 3 h
leads: 3 h, 6 h, 9 h
```

## O que já existe na branch

### Planejamento e composição sem efeitos colaterais

```text
monan_jedi_workflow/timeline.py
monan_jedi_workflow/cycle_plan.py
monan_jedi_workflow/components.py
monan_jedi_workflow/composition.py
monan_jedi_workflow/dry_run.py
```

Comandos existentes:

```bash
python scripts/monan-jedi-cycle-plan \
  configs/experiments/cycle_1day_3dfgat_x1.10242.yaml

python scripts/monan-jedi-cycle-dry-run \
  configs/experiments/cycle_1day_3dfgat_x1.10242.yaml
```

Esses comandos não criam arquivos e não submetem jobs.

### Componentes iniciais

```text
configs/assimilation/3dvar_fgat.yaml
configs/forecast/mpas_fgat_3h.yaml
configs/background/previous_forecast.yaml
configs/bmatrix/mpasstatic_x1.10242.yaml
configs/geometry/x1.10242.yaml
configs/platforms/jaci.yaml
configs/observations/conv_basic.yaml
configs/experiments/cycle_1day_3dfgat_x1.10242.yaml
```

O experimento de um dia ainda é um exemplo de planejamento e composição; ele
não é um caso executável no JACI.

## Doctor implementado

O `doctor` foi implementado como ferramenta estritamente somente de leitura:

```text
monan_jedi_workflow/doctor.py
scripts/monan-jedi-cycle-doctor
tests/test_doctor.py
docs/cycle-doctor.md
```

Uso:

```bash
python scripts/monan-jedi-cycle-doctor EXPERIMENT.yaml
```

Ele não cria arquivos, diretórios ou links; não renderiza YAML/PBS; não executa
MPAS ou MPAS-JEDI; e não chama `qsub`.

### Contrato declarativo

Cada item em `doctor.checks` declara:

```yaml
- name: recurso identificado para o relatório
  path: /caminho/para/recurso
  kind: file | directory | executable
  scope: once | cycle | trajectory   # opcional; padrão once
  access: [read, write, execute]     # opcional
```

São suportados:

- arquivos, diretórios e executáveis;
- permissões de leitura, escrita e execução;
- placeholders temporais por ciclo e por estado de trajetória FGAT;
- `{tasks}`, resolvido a partir de `run.tasks`;
- `{experiment_name}`, resolvido a partir de `experiment.name`.

Para a partição MPI, o padrão correto é:

```yaml
- name: partição compatível com run.tasks
  path: /caminho/x1.10242.graph.info.part.{tasks}
  kind: file
  access: [read]
```

Assim, `run.tasks: 64` exige `.part.64`; a existência de uma partição para
outro número de tarefas não é aceita.

Para estados FGAT, `scope: trajectory` expande para os estados planejados pelo
resolvedor temporal, por exemplo:

```yaml
- name: estados da trajetória FGAT
  path: /dados/states/{cycle_id}/x1.10242.init.{valid_mpas_time}.nc
  kind: file
  scope: trajectory
  access: [read]
```

A documentação completa está em `docs/cycle-doctor.md`.

## Cobertura de testes do doctor

`tests/test_doctor.py` cobre:

1. arquivo regular existente;
2. arquivo ausente, sem criá-lo;
3. diretório existente;
4. executável presente e ausente;
5. permissões declaradas;
6. partição selecionada por `run.tasks` e falha por incompatibilidade;
7. placeholders temporais para todos os estados FGAT previstos;
8. YAML inválido;
9. placeholder inválido;
10. garantia de que o filesystem não é modificado;
11. integração local da CLI com recursos temporários.

Validação efetivamente executada nesta sessão, em uma cópia temporária dos
arquivos publicados:

```text
python -m compileall -q monan_jedi_workflow scripts
python -m pytest -q tests/test_doctor.py
12 passed
```

A suíte completa do repositório **não foi reexecutada nesta sessão** porque o
ambiente de validação não conseguiu clonar o repositório por falha de resolução
de `github.com`. Não registrar uma aprovação de suíte completa sem executar,
num checkout real, o comando abaixo:

```bash
python -m pytest
```

## Commits do doctor

```text
ee54061 feat: add read-only cyclic doctor core
3247160 feat: add cyclic doctor command
da3ba8b test: cover read-only cyclic doctor
d30fb1 docs: describe read-only cyclic doctor
ab79924 feat: bind doctor partition checks to run tasks
335fb42 test: bind doctor partitions to declared tasks
82b9e9c docs: require task-aware doctor partition paths
```

## Próximo passo obrigatório

Antes de qualquer preparação de runtime, renderer ou PBS, executar em um
checkout normal:

```bash
python -m pytest
```

Critério de aceite: suíte completa aprovada.

Depois, no JACI e ainda sem criar runtime ou submeter jobs, preparar um YAML de
experimento com os paths reais e executar:

```bash
python scripts/monan-jedi-cycle-doctor EXPERIMENT.yaml
```

O YAML deve verificar, no mínimo:

- `mpasjedi_variational.x`;
- matriz B e seus metadados;
- invariante da geometria;
- partição com `{tasks}`;
- arquivos ou diretório de física;
- raízes/arquivos de observação;
- estados previstos da trajetória FGAT;
- permissões necessárias para leitura e para o futuro diretório de runtime.

Critério de aceite JACI: todos os checks passam sem criar recursos, renderizar
arquivos ou submeter job.

Somente depois disso, o próximo incremento de código é a preparação/renderização
incremental com comparação semântica ao baseline. Não modificar o renderer do
baseline até esse ponto.
