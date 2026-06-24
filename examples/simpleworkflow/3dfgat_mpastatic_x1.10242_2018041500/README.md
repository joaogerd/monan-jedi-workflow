# Exemplo MONAN-JEDI com simpleWorkflow

Execute a partir da raiz deste repositório:

```bash
simpleworkflow plan examples/simpleworkflow/3dfgat_mpastatic_x1.10242_2018041500/workflow.yaml
simpleworkflow run examples/simpleworkflow/3dfgat_mpastatic_x1.10242_2018041500/workflow.yaml \
  --workdir build/simpleworkflow/3dfgat_mpastatic_x1.10242_2018041500
```

O YAML apenas encadeia `validate-config`, `prepare-runtime`, `render-yaml`, `render-pbs`, `submit`, `wait` e `validate-run`.

`submit` persiste o Job ID no runtime e evita uma submissão PBS duplicada em retomadas. `wait` confirma apenas o término no scheduler. A confirmação científica ocorre em `validate-run`, conforme o contrato em `validation.yaml`.

Este exemplo é estático. A ciclagem temporal deve ser habilitada depois que as etapas de MPAS e Obs2IODA prepararem dados por ciclo.
