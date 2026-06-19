# Roadmap — Ciclo de Assimilação de Dados MONAN-JEDI

## Objetivo

Evoluir o `monan-jedi-workflow` de um renderer de um caso isolado e validado para um workflow reprodutível de assimilação de dados cíclica com MPAS-JEDI.

O alvo inicial é reproduzir, por configuração declarativa e renderização, o caso 3DVar-FGAT já validado com:

- malha `x1.10242`;
- ciclo inicial `2018041500`;
- execução MPI `np64`;
- matriz B estática já produzida para a malha e configuração do experimento;
- observações `Radiosonde`, `GnssroRefNCEP` e `SfcCorrected`.

Após reproduzir esse caso de forma automática, o workflow deverá evoluir para ciclos de 6 horas, inicialmente em um dia, depois em uma semana, um mês e finalmente em operação contínua.

## Princípios arquiteturais

1. O código Python é o motor do workflow; não deve conter configuração científica ou específica de um experimento.
2. Configurações científicas, de plataforma e de execução devem permanecer em YAMLs e templates versionados.
3. O YAML de experimento deve permanecer mínimo e expressar somente escolhas frequentes: método, observações, matriz B, horizonte temporal, recursos e poucos ajustes de minimização.
4. Arquivos renderizados são produtos do workflow e não fonte de verdade.
5. A configuração completa precisa ser resolvida, validada e gravada junto ao runtime para garantir reprodutibilidade.
6. A submissão PBS deve continuar explícita e controlada; a preparação/renderização não deve submeter jobs por padrão.
7. O ciclo deve ser idempotente: uma etapa já concluída não deve ser refeita sem solicitação explícita.

## Projetos a reaproveitar

### `monan-jedi-workflow`

Será o repositório e motor principal. Já possui os conceitos de validação, renderização de YAML/PBS, fragmentos de observações e variáveis, testes e CLI.

### `mpas-bmatrix-global`

Será a referência para reaproveitar e extrair componentes relacionados a:

- configuração operacional JACI;
- geração de namelist e streams do MPAS;
- preparação e execução de forecasts;
- renderização de PBS;
- convenções de diretórios, logs e produtos MPAS;
- caminhos e metadados da matriz B produzida.

A matriz B permanece um produto externo versionado por metadados e selecionado pelo experimento; a geração da B não deve ser incorporada ao ciclo de AD.

### `simpleWorkflow`

Será usado como referência conceitual para:

- representação de tarefas;
- dependências explícitas;
- controle de estado;
- detecção de tarefas prontas, concluídas ou bloqueadas.

Não é objetivo importar ou acoplar diretamente seu código antes de avaliar a compatibilidade. A implementação deverá ser adequada ao modelo de ciclos MPAS-JEDI e PBS.

### `NCAR/MPAS-Workflow`

Será a referência externa para a separação entre cenário/experimento, defaults, componentes configuráveis, observações e recursos de plataforma. A arquitetura local não precisa copiar a implementação, mas deve preservar o princípio de composição declarativa.

## Configuração proposta

### YAML mínimo do experimento

```yaml
experiment:
  name: cycle_1day_3dfgat_x1_10242

cycle:
  start: 2018-04-15T00:00:00Z
  end: 2018-04-16T00:00:00Z
  interval_hours: 6

assimilation:
  method: 3dvar_fgat
  outer_loops: 2
  inner_iterations: 50

forecast:
  profile: mpas_6h

background:
  source: previous_forecast
  initial: mpas_static_2018041500

bmatrix:
  name: mpasstatic_x1.10242

observations:
  set: conv_basic

geometry:
  name: x1.10242

run:
  platform: jaci
  tasks: 64
  walltime: "00:30:00"
```

Esse arquivo responde somente: **o que será executado**.

### Configuração detalhada por componente

```text
configs/
  experiments/
    cycle_1day_3dfgat_x1.10242.yaml

  assimilation/
    3dvar.yaml
    3dvar_fgat.yaml
    envar.yaml

  observations/
    sets/
      conv_basic.yaml
      conv_plus_satwind.yaml
    instruments/
      radiosonde.yaml
      gnssro_ref_ncep.yaml
      sfc_corrected.yaml
      aircraft.yaml
      satwind.yaml

  background/
    previous_forecast.yaml
    external_analysis.yaml
    mpas_static_initial.yaml

  bmatrix/
    mpasstatic_x1.10242.yaml

  geometry/
    x1.10242.yaml

  forecast/
    mpas_6h.yaml
    mpas_12h.yaml

  platforms/
    jaci.yaml

templates/
  jedi/
    3dvar.yaml.j2
    3dvar_fgat.yaml.j2
  mpas/
    namelist.atmosphere.j2
    streams.atmosphere.j2
  pbs/
    assimilation.pbs.j2
    forecast.pbs.j2
```

Cada arquivo de observação deve conter todos os detalhes técnicos do tipo observacional: fonte, template de arquivos, filtros, operadores, erros, variáveis, pré-processamento e parâmetros específicos do JEDI. Os conjuntos de observações apenas selecionam instrumentos.

## Modelo de composição

```text
experimento mínimo
  + método de assimilação
  + conjunto de observações
  + definições individuais de observação
  + estratégia de background
  + definição da B matrix
  + geometria
  + perfil de forecast
  + plataforma
  + overrides permitidos
  = configuração expandida e validada
  = YAML JEDI + namelist/streams MPAS + scripts PBS renderizados
```

A composição deve produzir dois artefatos distintos:

1. `resolved-config.yaml`: configuração completamente expandida, legível e validada.
2. arquivos runtime renderizados: YAML JEDI, arquivos MPAS e PBS usados naquele ciclo.

## Estrutura runtime proposta

```text
runs/
  cycle_1day_3dfgat_x1.10242/
    resolved-experiment.yaml
    2018041500/
      manifest.yaml
      background/
      observations/
      assimilation/
        resolved-config.yaml
        3dvar_fgat.yaml
        run_assimilation.pbs
      analysis/
      forecast/
        namelist.atmosphere
        streams.atmosphere
        run_forecast.pbs
      logs/
    2018041506/
      ...
```

Cada horário deve registrar um `manifest.yaml` com entradas, saídas esperadas, estado de cada etapa, hashes ou tamanhos dos arquivos críticos e vínculos para o ciclo anterior.

## Modelo de tarefas por horário

Para cada tempo de análise `T`:

```text
prepare(T)
  ├── resolve_observations(T)
  ├── resolve_background(T)
  ├── render_assimilation(T)
  ├── run_assimilation(T)
  ├── validate_analysis(T)
  ├── render_forecast(T)
  ├── run_forecast(T)
  └── validate_forecast(T)
```

Dependências:

```text
analysis(T) -> forecast(T, T+6h) -> background(T+6h) -> analysis(T+6h)
```

O primeiro ciclo usa o background inicial definido no experimento. Os seguintes usam o forecast do ciclo anterior, segundo a estratégia `previous_forecast`.

## Fases de implementação

### Fase 0 — Inventário e contrato de compatibilidade

- Mapear o caso baseline atualmente funcional, arquivo por arquivo.
- Identificar quais campos pertencem ao método, observações, B matrix, background, MPAS, plataforma e PBS.
- Definir um teste de equivalência: os arquivos renderizados pelo novo compositor devem ser semanticamente equivalentes aos arquivos manuais do baseline.
- Registrar caminhos e produtos mínimos necessários para o baseline.

**Critério de aceite:** inventário completo e baseline congelado como referência de regressão.

### Fase 1 — Compositor de configuração

- Implementar carregamento de YAMLs com composição e precedência documentada.
- Implementar seletores para método, observações, background, B matrix, geometria, forecast e plataforma.
- Manter suporte aos fragmentos existentes de variáveis e observadores.
- Gerar `resolved-config.yaml`.
- Validar chaves obrigatórias, referências inexistentes, tipos, datas e compatibilidade entre componentes.

**Critério de aceite:** o YAML mínimo do baseline gera uma configuração expandida válida sem detalhes científicos no código Python.

### Fase 2 — Renderer equivalente ao baseline

- Renderizar o YAML JEDI final do caso 3DVar-FGAT baseline.
- Renderizar `namelist.atmosphere` e `streams.atmosphere` para o forecast MPAS associado.
- Renderizar PBS de assimilação e forecast com dados da plataforma JACI.
- Criar testes de regressão comparando estrutura YAML e campos críticos com o caso manual validado.

**Critério de aceite:** caso único `2018041500` preparado automaticamente e pronto para ser submetido manualmente no JACI.

### Fase 3 — Primeiro encadeamento: 00Z → 06Z

- Implementar timeline de ciclos.
- Criar diretórios por tempo de análise.
- Resolver o forecast anterior como background do próximo ciclo.
- Implementar manifests e estado das etapas.
- Preparar e validar dois ciclos consecutivos sem submissão automática.

**Critério de aceite:** o segundo ciclo referencia exclusivamente os produtos corretos do primeiro forecast.

### Fase 4 — Um dia completo

- Preparar os horários 00Z, 06Z, 12Z e 18Z.
- Executar manualmente no JACI, com checagem de saídas entre ciclos.
- Registrar métricas de custo, convergência, observações utilizadas/rejeitadas e integridade dos restarts.

**Critério de aceite:** quatro ciclos concluídos e encadeados sem intervenção de edição de arquivos runtime.

### Fase 5 — Semana completa

- Adicionar retomada segura após falha.
- Adicionar verificação de produtos, logs e estados.
- Consolidar resumo por ciclo e por dia.
- Medir custo computacional e estabilidade operacional.

**Critério de aceite:** uma semana de ciclos com rastreabilidade completa e retomada de falhas validada.

### Fase 6 — Um mês e avaliação científica

- Executar aproximadamente um mês de ciclos de 6 horas.
- Gerar diagnósticos de função custo, O-B, O-A, incrementos, observações assimiladas/rejeitadas e falhas.
- Avaliar coerência física dos incrementos e estabilidade temporal.

**Critério de aceite:** relatório técnico/científico com resultados mensais e limitações identificadas.

### Fase 7 — Operação contínua

- Definir estratégia de disponibilidade de dados, atraso de observações e janela de recuperação.
- Implementar gatilho externo ou agendador para novos ciclos.
- Manter submissão explícita ou adicionar submissão controlada como opção separada.
- Criar monitoramento e alertas de falha.

**Critério de aceite:** ciclo contínuo com reinício seguro, rastreabilidade e operação documentada.

## Comandos desejados

```bash
# Validar e mostrar composição sem escrever runtime
monan-jedi-workflow cycle validate configs/experiments/cycle_1day_3dfgat_x1.10242.yaml

# Renderizar todos os arquivos de um experimento
monan-jedi-workflow cycle render configs/experiments/cycle_1day_3dfgat_x1.10242.yaml

# Mostrar o plano e as dependências sem executar
monan-jedi-workflow cycle plan configs/experiments/cycle_1day_3dfgat_x1.10242.yaml

# Preparar somente um ciclo
monan-jedi-workflow cycle prepare configs/experiments/cycle_1day_3dfgat_x1.10242.yaml --time 2018041500

# Preparar todo o período sem submeter jobs
monan-jedi-workflow cycle prepare configs/experiments/cycle_1day_3dfgat_x1.10242.yaml
```

A execução ou submissão deve permanecer separada:

```bash
qsub runs/.../run_assimilation.pbs
qsub runs/.../run_forecast.pbs
```

## Decisões iniciais

- Não criar novo repositório.
- Não acoplar geração de matriz B à execução cíclica.
- Não colocar filtros, operadores, caminhos detalhados, templates JEDI ou parâmetros científicos completos no YAML mínimo do experimento.
- Não fazer submissão automática como comportamento padrão.
- Não iniciar a ciclagem antes de reproduzir o baseline funcional por renderização.

## Próxima entrega

A próxima implementação deve começar pela Fase 0:

1. inventariar o diretório do baseline validado;
2. classificar cada arquivo/campo no componente correto;
3. definir a estrutura de YAMLs e templates sem quebrar os comandos atuais;
4. adicionar um teste de regressão que garanta equivalência do caso renderizado com o baseline manual.
