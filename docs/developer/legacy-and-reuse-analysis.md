# Análise de reaproveitamento dos workflows anteriores

Este documento existe para evitar a repetição do problema “já fizemos isso em algum workflow, mas não lembramos em qual”. Ele registra o papel de cada implementação anterior e o que deve ou não ser reaproveitado.

## `monan-jedi-workflow/main`

**Papel:** base oficial Python atual.

Reaproveitar:

- configuração por YAML;
- `CycleContext`;
- estágios MPAS e Obs2IODA cycle-aware;
- PBS explícito;
- validação separada;
- testes e CI.

Não criar uma segunda base concorrente.

## `monanwf-bash`

**Papel:** protótipo operacional simples do ciclo.

Reaproveitar como especificação:

- cadeia `AD -> forecast -> AD`;
- primeiro background externo;
- background posterior vindo do forecast anterior;
- dependências PBS explícitas;
- separação da campanha da B;
- ideia de runtime skeleton;
- validação de outputs;
- dry-run e rastreabilidade.

Não reaproveitar Bash como arquitetura principal.

## `feature/cycled-da-roadmap`

**Papel:** laboratório de arquitetura específico da ciclagem.

Minerar seletivamente:

- doctor;
- DAG/plan;
- manifests;
- modelo temporal;
- estratégia de testes;
- documentação de decisões.

Não fazer merge cego da branch: ela divergiu fortemente da `main` e contém decisões anteriores à implementação atual de MPAS/Obs2IODA.

## `architecture/v2-foundation` e `v2-mpas-forecast-stage`

**Papel:** tentativa de arquitetura V2 mais geral, com `core/`, `components/`, `platforms/`, `workflows/` e adapters de orquestração.

Essa linha é importante porque formalizou várias ideias que continuam corretas:

- stage científico independente do orquestrador;
- `WorkflowSpec` scheduler-neutral;
- adapter que gera `simpleWorkflow` sem executar ciência;
- separação entre plataforma/site e componente científico;
- artifacts, provenance, validation e persistent state como contratos explícitos;
- diferença entre término do scheduler e validação científica.

Ela **não é adotada integralmente nesta fase** porque isso implicaria migrar uma arquitetura inteira (~300 commits divergentes) antes de provar o ciclo mínimo de assimilação. O objetivo atual é menor: completar a ciclagem sobre a `main` com stages explícitos e documentação clara.

Os conceitos devem ser minerados progressivamente. Se a implementação simples começar a duplicar serviços gerais (artifact model, platform abstraction, workflow-spec rendering), a V2 é a primeira fonte a consultar antes de criar nova abstração.

### Teste V2 órfão na `main`

O commit final da `main` antes deste trabalho adicionou `tests/test_v2_jaci_wait_progress.py`, mas não adicionou os módulos `monan_jedi_workflow.platforms` e `core.progress` dos quais o teste depende. Isso deixava o CI da `main` sem coletar a suíte.

A branch de desenvolvimento do cycling remove esse teste órfão em vez de importar parcialmente a V2 apenas para satisfazê-lo. Se a plataforma V2 for migrada no futuro, o teste deve retornar junto com a implementação completa correspondente.

## `simpleWorkflow`

**Papel:** orquestrador leve de referência para pesquisa.

Usar:

- DAG;
- expansão de ciclos;
- estado/restart;
- logs por tentativa;
- proveniência;
- validação de artefatos;
- execução local/PBS quando útil.

Não importar `simpleWorkflow` dentro dos módulos de domínio.

## `monan-jedi-workflow_v0`

**Papel:** histórico da primeira migração, inclusive ideias de site/JACI e Cylc.

Manter como referência histórica; não voltar à implementação antiga nem tornar Cylc dependência obrigatória.

## Tutorial GAD/INPE de Cycling DA

**Papel:** referência conceitual para entender o ciclo completo e o conjunto de artefatos.

Usar para perguntar “qual função esta etapa cumpre?”. Não copiar diretamente YAML, scripts, executáveis ou convenções de uma versão anterior do MPAS-JEDI.

## Regra de fonte de verdade

Quando referências divergem, a prioridade é:

```text
1. baseline atual que executa com a versão atual do MONAN-JEDI
2. interfaces do código MONAN-JEDI/MPAS atual
3. monan-jedi-workflow atual
4. protótipos/branches de desenvolvimento
5. tutoriais históricos
```
