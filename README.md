# MONAN-JEDI Workflow

Workflow Python-first para executar e validar etapas do MONAN/MPAS-JEDI sem acoplar a ciência a um orquestrador específico.

O projeto separa duas responsabilidades:

```text
monan-jedi-workflow                 orquestrador
-------------------                 -----------
como preparar/executar              quando executar
como validar                        dependências
inputs/outputs do domínio           ciclos, restart, estado

                                    simpleWorkflow (pesquisa)
                                    ecFlow (operação INPE)
                                    Cylc (possível alternativa)
```

A regra principal é simples: **as etapas de domínio devem funcionar sozinhas pela CLI**. `simpleWorkflow`, ecFlow ou Cylc apenas organizam essas mesmas etapas.

## Estado atual

O repositório possui estágios cycle-aware para:

- MPAS;
- Obs2IODA;
- MPAS-JEDI (análise);
- preparação WPS/condição inicial MPAS já existente no fluxo de dados.

A nova interface JEDI é:

```bash
monan-jedi-workflow jedi-prepare  CASE --cycle 2018-04-15T00:00:00Z
monan-jedi-workflow jedi-submit   CASE --cycle 2018-04-15T00:00:00Z
monan-jedi-workflow jedi-wait     CASE --cycle 2018-04-15T00:00:00Z
monan-jedi-workflow jedi-validate CASE --cycle 2018-04-15T00:00:00Z
```

Esses comandos não executam o workflow completo. Isso é intencional.

## Instalação

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

Para desenvolvimento:

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

## Primeiro ciclo

Um caso cíclico contém, no mínimo:

```text
CASE/
  jedi.yaml
  mpas.yaml
  obs2ioda.yaml
  workflow.yaml
```

Antes de executar:

```bash
monan-jedi-workflow cycle-doctor CASE \
  --cycle 2018-04-15T00:00:00Z
```

Com `simpleWorkflow` instalado:

```bash
swf plan CASE/workflow.yaml

swf run CASE/workflow.yaml \
  --cycle-time 2018-04-15T00:00:00Z

swf status CASE/workflow.yaml
```

O exemplo de referência está em:

```text
examples/simpleworkflow/cycled_da/
```

> Os arquivos científicos do exemplo são templates. Caminhos, nomes de outputs, YAML variacional, namelists, streams e arquivos de malha devem ser ajustados ao **baseline atual validado** antes da primeira execução no JACI.

## Matriz B

A geração da B não faz parte do workflow de cycling. O ciclo consome uma B previamente construída e validada. Isso permite que `MPAS-BMatrix` e a campanha de assimilação evoluam independentemente e preserva a identidade da B usada em cada experimento.

## Documentação

### Usuário

Comece por:

- [Primeiro experimento cíclico](docs/user/first-cycling-experiment.md)
- [Configuração de um caso](docs/user/case-configuration.md)
- [Status e restart](docs/user/restart-and-status.md)
- [Troubleshooting](docs/user/troubleshooting.md)

A documentação de usuário é propositalmente curta e orientada a tarefas.

### Desenvolvedor

A documentação interna registra arquitetura, contratos e decisões:

- [Orquestração](docs/developer/orchestration.md)
- [Modelo temporal](docs/developer/cycle-time-model.md)
- [Estágio JEDI](docs/developer/jedi-stage.md)
- [Modelo conceitual do ciclo](docs/developer/reference-cycle-model.md)
- [Reaproveitamento de workflows anteriores](docs/developer/legacy-and-reuse-analysis.md)
- [Política de documentação](docs/developer/documentation-policy.md)
- [ADRs](docs/developer/adr/README.md)

## Baseline estático anterior

Os comandos anteriores (`validate-config`, `prepare-runtime`, `render-yaml`, `render-pbs`, `submit`, `wait`, `validate-run`) continuam disponíveis para reproduzir e depurar o baseline estático. O caminho cíclico novo não remove essa interface; ele acrescenta stages explícitos por ciclo.

## Segurança operacional

Preparação e renderização não submetem jobs implicitamente. A primeira operação que chama `qsub` é sempre um comando de submissão explícito (`*-submit`). Término no PBS e sucesso científico são estados diferentes: use sempre `*-validate`.
