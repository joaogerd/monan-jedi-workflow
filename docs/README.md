# Documentação do MONAN-JEDI Workflow

A documentação é separada por público para evitar que o caminho simples do usuário seja soterrado por detalhes de implementação.

## Para usar o workflow

1. [Primeiro experimento cíclico](user/first-cycling-experiment.md)
2. [Configuração de um caso](user/case-configuration.md)
3. [Status e restart](user/restart-and-status.md)
4. [Troubleshooting](user/troubleshooting.md)

Esses documentos devem permanecer curtos, com comandos copiáveis e foco em tarefas.

## Para desenvolver o workflow

Comece pela fronteira de arquitetura e pelos contratos; depois leia a implementação específica do JEDI.

1. [Arquitetura de orquestração](developer/orchestration.md)
2. [Contratos das etapas de domínio](developer/stage-contracts.md)
3. [Portabilidade simpleWorkflow → ecFlow/Cylc](developer/orchestrator-portability.md)
4. [Modelo temporal do ciclo](developer/cycle-time-model.md)
5. [Modelo conceitual de Cycling DA](developer/reference-cycle-model.md)
6. [Mapeamento do baseline que passou para o ciclo](developer/baseline-to-cycling-mapping.md)
7. [Estágio JEDI](developer/jedi-stage.md)
8. [Plano de validação no JACI](developer/jaci-validation-plan.md)
9. [Reaproveitamento dos workflows anteriores](developer/legacy-and-reuse-analysis.md)
10. [Handoff analysis → forecast MPAS](developer/analysis-to-mpas-forecast-handoff.md)
10. [Política de documentação](developer/documentation-policy.md)
11. [Architecture Decision Records](developer/adr/README.md)

A documentação de desenvolvedor pode e deve ser detalhada. Ela registra contratos, invariantes, efeitos colaterais e motivos das decisões.

## Documentos técnicos anteriores

Os documentos existentes sobre baseline estático, Obs2IODA, WPS, MPAS e investigação histórica continuam úteis. Quando houver conflito entre um texto antigo e a nova documentação de arquitetura, considere como fonte de verdade o baseline atual validado e os ADRs aceitos.

O documento [Etapas cíclicas de domínio](cycle-stage-configuration.md) resume a relação entre MPAS, Obs2IODA, JEDI e o `simpleWorkflow`.
