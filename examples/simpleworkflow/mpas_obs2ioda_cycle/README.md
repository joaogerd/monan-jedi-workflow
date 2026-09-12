# MPAS + Obs2IODA (exemplo pré-assimilação)

Este exemplo é mantido para testar somente a preparação de background MPAS e observações Obs2IODA em ciclos. Ele **não é** o exemplo principal de Cycling DA completo.

Para análise -> forecast -> próximo ciclo, use:

```text
examples/simpleworkflow/cycled_da/
```

O workflow deste exemplo reduzido continua útil para validar MPAS e Obs2IODA independentemente do JEDI.

## Pré-requisitos

- `simpleWorkflow` instalado;
- `monan-jedi-workflow` no `PATH`;
- `mpas.yaml` e `obs2ioda.yaml` configurados;
- ambiente JACI carregado quando os executáveis dependem do stack HPC.

## Uso

```bash
swf plan cases/mpas_obs2ioda_x1.10242/simpleworkflow.yaml
swf run  cases/mpas_obs2ioda_x1.10242/simpleworkflow.yaml
swf status cases/mpas_obs2ioda_x1.10242/simpleworkflow.yaml
```

Não use este exemplo reduzido como especificação da ordem operacional do ciclo completo.
