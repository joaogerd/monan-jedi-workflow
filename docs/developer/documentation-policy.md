# Política de documentação

O projeto mantém documentação em duas camadas porque usuário e desenvolvedor têm necessidades diferentes.

## Documentação do usuário

Deve ser:

- curta;
- orientada a tarefas;
- baseada em comandos copiáveis;
- explícita sobre pré-requisitos e outputs;
- sem histórico arquitetural desnecessário.

Um usuário deve conseguir executar o caso de referência sem ler o código-fonte.

## Documentação do desenvolvedor

Deve ser deliberadamente detalhada. O objetivo não é somente dizer **o que** o código faz, mas preservar **por que** ele foi desenhado assim.

Todo módulo importante deve documentar:

1. responsabilidade;
2. não responsabilidade;
3. modelo conceitual;
4. entradas e saídas;
5. invariantes;
6. efeitos colaterais;
7. idempotência/restart;
8. decisões de arquitetura;
9. falhas esperadas;
10. relação com outros módulos.

## Docstrings públicas

Funções/classes públicas devem, quando aplicável, explicar:

- parâmetros;
- retorno;
- arquivos lidos/escritos;
- side effects;
- comportamento em reexecução;
- erros relevantes;
- convenções científicas de tempo/malha/variáveis.

Comentários inline devem explicar principalmente **por que** uma escolha não óbvia existe. Evite comentários que apenas repetem a linha seguinte.

## Architecture Decision Records

Decisões que restringem a evolução futura precisam de ADR. Exemplos:

- independência de orquestrador;
- papel do simpleWorkflow;
- B como artefato externo ao ciclo;
- análise como referência temporal do ciclo.

## Definition of Done

Uma mudança que altera comportamento público só está pronta quando inclui, conforme aplicável:

- implementação;
- testes;
- `--help`/CLI;
- documentação do usuário;
- documentação de desenvolvedor;
- docstrings;
- exemplo executável ou template;
- ADR para nova decisão arquitetural;
- comportamento de falha/restart testado.
