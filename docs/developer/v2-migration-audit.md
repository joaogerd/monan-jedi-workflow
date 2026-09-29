# Auditoria da linha V2 e matriz de migração

## Objetivo

Este documento encerra a ambiguidade sobre os PRs históricos #42, #45, #46 e
#48. Eles contêm trabalho útil, mas não formam uma mudança que possa ser
mesclada com segurança sobre a `main` atual.

A regra é:

> **A `main` é a única base de implementação. A linha V2 é uma fonte de
> contratos e componentes a serem migrados seletivamente, com novos testes e
> validação contra a arquitetura e o runtime contract atuais.**

Nenhum arquivo deve ser copiado apenas para "preservar" código. Uma migração
precisa resolver uma necessidade atual e obedecer à Definition of Done vigente.

## Relação entre os PRs históricos

| PR | Papel histórico | Relação |
|---|---|---|
| #42 | primeira fundação declarativa MPAS/NMC | linha anterior e parcialmente concorrente |
| #45 | fundação arquitetural V2 | base conceitual da V2 |
| #46 | contrato NMC pairs | extensão de #45 |
| #48 | MPAS/WPS/JACI/NMC execution stack | extensão empilhada sobre #46 |

#48 não é um PR independente contra a `main`: sua base declarada é a branch
de #46. #46, por sua vez, incorpora a fundação de #45. Portanto, revisar os
quatro como patches independentes superestima mudanças e esconde dependências.

## Matriz de decisão

| Capacidade histórica | Situação na `main` | Decisão |
|---|---|---|
| stage científico independente do orquestrador | **absorvida** | manter a implementação cycle-aware atual |
| `prepare -> submit/run -> wait -> validate` | **absorvida** | contrato atual é fonte de verdade |
| diferença scheduler completion / scientific validation | **absorvida** | manter; não portar implementação duplicada |
| configuração declarativa e resolução temporal | **absorvida** | manter `CycleContext`, `stage_config` e YAML atual |
| runtime/site sem caminhos privados do produtor | **absorvida e evoluída** | usar runtime contract v2 atual |
| inputs locais/remotos e decisão WPS | **parcialmente absorvida** | evoluir `mpas_pipeline`; não restaurar #42 |
| plano de stages/dependências | **parcialmente absorvida** | `mpas_pipeline.StagePlan` + simpleWorkflow; evitar segundo DAG interno agora |
| estado/restart | **absorvido em outra camada** | simpleWorkflow é dono do estado do workflow; domínio mantém manifests próprios |
| `WorkflowSpec` / `StageSpec` genéricos | **ausente** | migrar somente se houver dois ou mais consumidores reais que justifiquem a abstração |
| `ValidationReport` estruturado comum | **ausente** | candidato a migração; requer adaptação dos validators atuais |
| modelo comum de `Artifact` + checksum | **parcial** | candidato quando contratos entre stages exigirem identidade/proveniência comum |
| provenance writer genérico | **parcial** | consolidar somente após mapear manifests atuais |
| adapter Python que renderiza simpleWorkflow | **não necessário hoje** | workflow YAML/simpleWorkflow já é a camada externa; não duplicar o orquestrador |
| plataforma JACI abstrata | **parcialmente absorvida** | extrair apenas quando reduzir duplicação real entre stages |
| backend local/JACI por `ExecutionRequest` | **ausente** | candidato de médio prazo, não requisito do ciclo atual |
| progress reporter scheduler-neutral | **ausente** | candidato útil para jobs longos; migrar junto do backend, não isoladamente |
| MPAS forecast product identity | **parcialmente absorvida** | comparar com `mpas_stage` antes de criar modelo adicional |
| MPAS forecast/init staging e validation V2 | **parcialmente absorvida** | minerar invariantes/testes; não substituir stages validados em bloco |
| NetCDF structural/semantic contracts | **ausente/parcial** | **alta prioridade para reaproveitamento**, especialmente tempo, malha e produtos MPAS |
| WPS product contract | **parcialmente absorvida** | minerar validações que ainda não existam |
| NMC f048/f024 pair model | **ausente na linha operacional atual** | **preservar como requisito futuro da B-matrix** |
| BFLOW manifest hand-off | **ausente** | **preservar e migrar quando a campanha NMC for retomada** |
| NMC campaign planner | **ausente** | recuperar a partir de #42/#46/#48 quando integrar geração de amostras B |
| JACI filesystem/scheduler/launcher policies | **parcialmente absorvidas** | portar somente regras ainda não cobertas pelo runtime contract/PBS atual |
| V2 CLI paralela | **obsoleta como interface** | novas capacidades entram na CLI atual; não criar `monan-jedi-workflow-v2` |
| exemplos V2 completos | **históricos** | recriar exemplos sobre YAML/CLI atuais quando a capacidade correspondente migrar |

## Conteúdo que deve ser recuperado primeiro

### 1. Contratos NetCDF científicos

Os testes e módulos de #48 para estrutura NetCDF, horário MPAS e validação de
outputs atacam um problema de domínio que não deve ficar delegado apenas a
"arquivo existe". A migração deve:

1. partir da `main`;
2. usar as convenções temporais atuais;
3. produzir erros estruturados e claros;
4. ser aplicada primeiro a MPAS init/forecast;
5. incluir testes unitários sem JACI e uma validação real no JACI antes de ser
   considerada concluída.

### 2. Contrato NMC f048/f024 -> BFLOW

#42, #46 e #48 preservam a lógica de pareamento por **valid time**, não apenas
por nome de arquivo. Esse conceito deve ser mantido para a retomada da
B-matrix.

O produtor é o workflow MPAS. O consumidor é MPAS-BMatrix. A interface futura
deve ser um manifesto explícito e versionado; o consumidor não deve inferir
diretórios privados do produtor.

### 3. Relatórios estruturados de validação

A V2 introduziu `ValidationReport`. A `main` atual tem validators específicos
e mensagens úteis, mas não um resultado comum. A abstração só deve ser migrada
se puder unificar resultados sem enfraquecer as mensagens específicas de
MPAS/JEDI/Obs2IODA.

### 4. Backend/progresso de execução

A separação `ExecutionRequest -> backend local/JACI` e o progress reporter de
#48 são úteis, mas devem vir depois dos contratos científicos. O scheduler não
pode voltar a ser fonte de "sucesso científico".

## Conteúdo que não deve ser portado

- a CLI paralela `monan-jedi-workflow-v2`;
- uma segunda árvore completa `core/components/platforms/workflows` apenas por
  simetria arquitetural;
- estado de workflow duplicando o SQLite/simpleWorkflow;
- paths, módulos ou defaults JACI anteriores ao runtime contract v2;
- configuração que reconstrua o stack em vez de consumir
  `MONAN_JEDI_INSTALL_ROOT` + `STACK_ROOT` e o manifesto instalado;
- código de #42 que duplique o `mpas_pipeline` atual;
- branches empilhadas ou commits históricos como base de novos PRs.

## Procedimento obrigatório para migração

Cada item recuperado da V2 deve ser um PR novo criado da `main` e declarar:

1. PR/arquivo histórico usado como referência;
2. lacuna concreta da `main` que está sendo resolvida;
3. contrato público resultante;
4. testes locais;
5. impacto sobre YAML/CLI/documentação;
6. compatibilidade com runtime contract v2;
7. validação JACI quando houver comportamento HPC;
8. documentação de usuário e desenvolvedor correspondente.

## Critério para encerrar #42/#45/#46/#48

Os PRs históricos podem ser fechados sem perda de conhecimento quando:

- esta matriz estiver integrada à `main`;
- cada PR receber comentário apontando para esta auditoria;
- ficar explícito que fechamento **não significa que todo o conteúdo foi
  implementado**;
- as capacidades marcadas para recuperação permanecerem registradas aqui.

Depois disso, novas mudanças devem partir exclusivamente da `main`.
