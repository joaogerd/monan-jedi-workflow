# Manifestos de estágio

`monan_jedi_workflow.manifest` define registros de proveniência para cada
tentativa de estágio de um ciclo.

O manifesto responde à pergunta:

```text
com quais configurações, entradas, argumentos e saídas este estágio foi criado?
```

Ele é complementar ao banco do orquestrador. O banco informa o estado operacional
da tarefa; o manifesto preserva a rastreabilidade científica do produto.

## Campos principais

Cada manifesto registra:

- `experiment`;
- `cycle_id`;
- `stage`;
- `attempt`;
- `status`: `planned`, `running`, `success` ou `failed`;
- `created_at` e `updated_at` em UTC;
- hash SHA-256 da configuração resolvida;
- `argv` planejado;
- executor planejado;
- futuro `scheduler_job_id`;
- fingerprints de entradas e saídas;
- metadados adicionais.

## Escrita

`write_manifest()` grava o YAML de forma atômica usando um arquivo temporário
irmão e troca final por `replace()`.

A criação de manifestos não executa MPAS, MPAS-JEDI, conversores, comandos MPI
ou PBS. Ela apenas materializa registros de proveniência.
