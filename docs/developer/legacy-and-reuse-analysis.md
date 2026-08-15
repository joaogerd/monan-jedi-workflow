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

**Papel:** laboratório de arquitetura.

Minerar seletivamente:

- doctor;
- DAG/plan;
- manifests;
- modelo temporal;
- estratégia de testes;
- documentação de decisões.

Não fazer merge cego da branch: ela divergiu fortemente da `main` e contém decisões anteriores à implementação atual de MPAS/Obs2IODA.

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
4. protótipos locais
5. tutoriais históricos
```
