# ADR 0005 — Campanhas usam ciclos nativos do simpleWorkflow

## Estado

Aceito para a nova interface de campanhas.

## Contexto

A primeira campanha multi-ciclo materializava em Python uma cópia completa das tarefas para cada horário. Isso tornava o `workflow.yaml` proporcional à duração da campanha e misturava definição do processo com instâncias de execução.

O `simpleWorkflow` possui agora uma fase `initialization`, ciclo temporal inclusivo, contexto de posição e seletores fechados de ciclo. Essas capacidades permitem representar o processo uma única vez.

## Decisão

O `monan-jedi-workflow` gera um `workflow.yaml` de tamanho estrutural constante:

- `initialization.tasks` contém a integração MPAS executada uma única vez para produzir o primeiro background;
- `cycle` contém apenas `start`, `end` e `step`;
- `tasks` contém uma única definição de background, observações, JEDI, MPAS e publicação do background seguinte;
- timestamps vêm do contexto do ciclo e não dos IDs das tarefas;
- backgrounds são normalizados em `work/background/<cycle_id>/`;
- `next_background` é `not_last`;
- MPAS no último ciclo é controlado pela configuração científica, não por regra fixa do gerador;
- uma integração MPAS longa pode fornecer simultaneamente +6 h para a ciclagem e prazos adicionais de previsão.

## Dependência temporal

Os ciclos do `simpleWorkflow` são sequenciais e restart-safe. A publicação do background seguinte pertence ao ciclo produtor; o próximo ciclo só começa depois da conclusão do anterior. Assim JEDI(t+6) não pode anteceder a produção determinística de background(t+6).

## Consequências

O período da campanha deixa de controlar a quantidade estrutural de tarefas. Campanhas de 3 dias, 7 dias, 30 dias e 365 dias possuem o mesmo conjunto de IDs de tarefas; variam somente os limites temporais e o número de instâncias persistidas no estado do executor.

A fase inicial exige uma condição inicial MPAS válida anterior ao primeiro horário de análise. Esse é um input científico/site-specific e deve ser validado no preflight; ele não pode ser substituído por um background do primeiro ciclo previamente calculado fora da campanha.