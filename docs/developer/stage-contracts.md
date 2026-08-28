# Contratos das etapas de domínio

Este documento define a interface estável entre o `monan-jedi-workflow` e qualquer orquestrador externo. O objetivo é permitir que a mesma implementação científica seja chamada por `simpleWorkflow`, ecFlow, Cylc, scripts de diagnóstico ou diretamente pelo pesquisador.

## Princípio

Uma etapa é uma unidade de domínio com entradas e saídas explícitas. O orquestrador pode saber **que** a etapa existe e **de qual etapa depende**, mas não deve precisar conhecer como ela constrói seus runtimes ou interpreta os arquivos científicos.

## Lifecycle recomendado

Para stages executados via scheduler:

```text
prepare -> submit -> wait -> validate
```

Para stages locais, como muitos conversores de observação:

```text
preflight/doctor -> prepare -> run -> validate
```

### `prepare`

Responsável por materializar deterministicamente o runtime:

- resolver configuração;
- verificar entradas imediatamente necessárias;
- criar diretórios;
- criar links seguros;
- renderizar templates;
- escrever PBS quando aplicável;
- registrar proveniência suficiente para uma reexecução segura.

**Não pode submeter job.**

### `submit` / `run`

É a operação que inicia trabalho computacional.

`submit` pode ter efeitos no scheduler e deve registrar um identificador persistente. Reexecução sem flag explícita não pode criar silenciosamente uma segunda submissão da mesma etapa.

`run` executa uma operação síncrona/local.

### `wait`

Observa somente o backend de execução. A saída do scheduler da fila significa que o backend terminou de acompanhá-lo; não significa que os produtos científicos estejam válidos.

### `validate`

Verifica o contrato de saída do domínio, por exemplo:

- marcadores de log;
- existência e tamanho de arquivos;
- estrutura NetCDF/HDF5 quando declarada;
- horário esperado;
- variáveis/dimensões exigidas pelo consumidor.

Somente depois dessa etapa um produto deve ser publicado como artefato válido.

## Contrato de processo

Todos os comandos públicos devem obedecer:

- `exit code 0`: a operação solicitada completou seu próprio contrato;
- `exit code != 0`: o orquestrador deve considerar a tarefa falha;
- stdout/stderr devem ser úteis para humanos e permanecer estáveis o suficiente para logs;
- sucesso científico nunca deve depender apenas do exit code do executável externo.

## Contrato de filesystem

Cada ciclo deve escrever em um diretório determinístico e não compartilhar outputs mutáveis com outro ciclo.

Para JEDI:

```text
work/jedi/<cycle_id>/
  variational.yaml
  run_jedi.pbs
  ...scientific runtime...
  .monan-jedi-workflow/
    jedi-submission.json
    jedi-validation.json
    jedi-artifacts.json
```

Para MPAS e Obs2IODA, a mesma regra se aplica aos manifests específicos já existentes.

## Manifests de domínio versus estado do orquestrador

São camadas diferentes:

```text
stage manifest
  prova o que o domínio preparou/validou

simpleWorkflow/ecFlow state
  prova o que o orquestrador tentou/executou
```

Nunca use somente o estado do orquestrador para inferir que um arquivo científico continua válido.

## Artifact manifest

Quando um produto será consumido fora do estágio que o criou, prefira publicar um pequeno manifesto com papel semântico:

```json
{
  "schema_version": 1,
  "producer": "monan-jedi-workflow:jedi",
  "cycle_time": "2018-04-15T00:00:00Z",
  "valid": true,
  "artifacts": [
    {
      "role": "analysis",
      "path": "/.../analysis.nc",
      "exists": true
    }
  ]
}
```

O consumidor não deve precisar descobrir o analysis parsing um log.

## Idempotência

Uma operação deve ser explicitamente classificada:

- **idempotente**: pode ser repetida sem mudar o resultado lógico;
- **reutilizável com estado**: repete somente se o estado/produto deixou de ser válido;
- **side-effectful**: requer uma flag explícita para repetir (`--resubmit`, `--force`).

No estágio JEDI atual:

| Operação | Comportamento de repetição |
|---|---|
| `jedi-prepare` | reutiliza links/skeleton compatíveis e rerenderiza determinísticamente |
| `jedi-submit` | reutiliza Job ID; `--resubmit` cria novo job |
| `jedi-wait` | pode observar novamente o Job ID registrado |
| `jedi-validate` | pode validar novamente os mesmos produtos |

## Requisitos para uma nova etapa

Antes de expor uma nova etapa a um orquestrador, documente:

1. significado científico;
2. unidade temporal (`analysis time`, `forecast init`, `valid time` etc.);
3. inputs obrigatórios;
4. outputs publicados;
5. efeitos colaterais;
6. comportamento de restart/reexecução;
7. condições de validação;
8. recursos/scheduler quando aplicável;
9. exemplos de chamada direta;
10. testes de sucesso e dos principais modos de falha.
