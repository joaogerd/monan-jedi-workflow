# ADR 0001 — Independência de orquestrador

**Status:** accepted

## Contexto

A operação do INPE usa ecFlow. O desenvolvimento científico não precisa de toda a infraestrutura de um gerenciador operacional de centro, mas amarrar o MONAN-JEDI a outro orquestrador obrigaria a operação a reescrever lógica de domínio durante a transição.

## Decisão

O `monan-jedi-workflow` não dependerá de simpleWorkflow, ecFlow, Cylc ou outro motor para implementar etapas científicas.

A unidade pública de integração é uma etapa cycle-aware chamável por CLI e com inputs/outputs verificáveis.

## Consequências

- pesquisa e operação podem usar orquestradores diferentes;
- o workflow e suas dependências podem ser reexpressos sem reimplementar runtime científico;
- cada etapa precisa de contrato mais explícito;
- não haverá um motor de workflow escondido dentro do pacote de domínio.
