# Registros de decisões arquiteturais (ADRs)

Um ADR registra **o que foi decidido e quando**, mas não é necessariamente a interface atualmente implementada. Para o contrato operacional do branch consulte a [arquitetura verificada](../architecture.md).

| ADR | Assunto | Situação frente à implementação atual |
| --- | --- | --- |
| [0001](0001-orchestrator-independence.md) | Independência dos estágios científicos em relação ao orquestrador | Princípio arquitetural mantido |
| [0002](0002-simpleworkflow-reference-orchestrator.md) | simpleWorkflow na pesquisa | Implementado como motor de referência |
| [0003](0003-bmatrix-external-artifact.md) | Matriz B como artefato científico externo | Princípio mantido |
| [0004](0004-analysis-centred-time.md) | Ciclo centrado na hora de análise | Princípio mantido |
| [0005](0005-native-cycle-campaigns.md) | Campanhas com DAG estruturalmente constante | **Direção futura, não implementada** no exportador `platform_campaign.py` |

Ao desenvolver funcionalidades, não trate um documento de intenção como prova de execução científica. Divergências entre ADR e código devem ser registradas como pendências, com testes e migração antes de mudar a documentação operacional.
