# Documentação do MONAN-JEDI Workflow

A documentação é separada por público para evitar que o caminho simples do usuário seja soterrado por detalhes de implementação.

## Para usar o workflow

1. [Primeiro experimento cíclico](user/first-cycling-experiment.md)
2. [Configuração de um caso](user/case-configuration.md)
3. [Status e restart](user/restart-and-status.md)
4. [Troubleshooting](user/troubleshooting.md)

Esses documentos devem permanecer curtos, com comandos copiáveis e foco em tarefas.

## Para desenvolver o workflow

1. [Arquitetura de orquestração](developer/orchestration.md)
2. [Modelo temporal do ciclo](developer/cycle-time-model.md)
3. [Estágio JEDI](developer/jedi-stage.md)
4. [Modelo conceitual de Cycling DA](developer/reference-cycle-model.md)
5. [Reaproveitamento dos workflows anteriores](developer/legacy-and-reuse-analysis.md)
6. [Política de documentação](developer/documentation-policy.md)
7. [Architecture Decision Records](developer/adr/README.md)

A documentação de desenvolvedor pode e deve ser detalhada. Ela registra contratos, invariantes e motivos das decisões.

## Documentos técnicos anteriores

Os documentos existentes sobre baseline estático, Obs2IODA, WPS, MPAS e investigação histórica continuam úteis. Quando houver conflito entre um texto antigo e a nova documentação de arquitetura, considere como fonte de verdade o baseline atual validado e os ADRs aceitos.

O documento [Etapas cíclicas de domínio](cycle-stage-configuration.md) resume a relação entre MPAS, Obs2IODA, JEDI e o `simpleWorkflow`.
