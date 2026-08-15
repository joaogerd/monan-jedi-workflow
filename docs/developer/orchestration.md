# Arquitetura de orquestração

## Decisão central

O `monan-jedi-workflow` é uma biblioteca/CLI de **domínio**. Ele conhece MPAS, JEDI, Obs2IODA, contratos de runtime e validação. Ele não é o dono da DAG de produção.

A orquestração pertence a uma camada externa:

```text
                        DOMAIN
              monan-jedi-workflow
           prepare / submit / wait / validate
                         |
            +------------+------------+
            |            |            |
      simpleWorkflow   ecFlow        Cylc
        pesquisa       operação      alternativa
```

`simpleWorkflow` é a implementação de referência para pesquisa porque fornece DAG, ciclos, estado, restart, logs e proveniência sem exigir a infraestrutura de um gerenciador operacional de centro inteiro.

No INPE, a operação pode reproduzir a mesma DAG em ecFlow. Essa migração não deve exigir reimplementar lógica científica ou scripts de runtime.

## Fronteira de responsabilidades

### O domínio decide

- como preparar um runtime;
- quais arquivos são entradas de uma etapa;
- como renderizar YAML/namelist/streams;
- qual executável chamar;
- como validar outputs;
- quais artefatos publicar;
- como interpretar os horários científicos do ciclo.

### O orquestrador decide

- quando uma tarefa pode iniciar;
- dependências entre tarefas;
- sequência de ciclos;
- retries/restart de tarefas;
- política de execução do workflow;
- visualização operacional.

## Contrato mínimo de uma etapa

Uma etapa cíclica deve possuir operações separáveis:

```text
prepare -> submit/run -> wait -> validate
```

Nem toda etapa precisa de PBS (Obs2IODA pode executar localmente), mas as responsabilidades devem continuar explícitas.

### Por que separar `wait` e `validate`

Um scheduler sabe que o processo terminou; ele não sabe se o resultado científico esperado existe ou é utilizável. A validação de domínio precisa continuar independente.

## Mapeamento conceitual

| MONAN-JEDI | simpleWorkflow | ecFlow | Cylc |
|---|---|---|---|
| stage | task | task | task |
| dependency | `depends_on` | trigger | graph dependency |
| cycle time | cycle context | repeat/date | cycling point |
| successful output | artifact validation | task/script check | task/script check |
| restart | state database | server state | run database |
| stage manifest | file artifact | file artifact | file artifact |

O mapeamento não precisa ser bit a bit. O requisito é que a mesma etapa de domínio possa ser chamada pelos três ambientes.

## Anti-patterns

Não faça:

- importar `simpleWorkflow` dentro de módulos científicos;
- chamar ecFlow dentro de `jedi_stage.py`;
- codificar a DAG completa em `cycle-run` dentro do pacote de domínio;
- esconder `qsub` dentro de um comando de preparação;
- considerar retorno do PBS como substituto da validação científica.

## Teste de independência

Toda etapa nova deve ser testável diretamente pela CLI, sem que `swf`, ecFlow ou Cylc estejam instalados.
