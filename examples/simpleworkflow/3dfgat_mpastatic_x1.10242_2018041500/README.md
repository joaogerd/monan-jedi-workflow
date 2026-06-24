# Exemplo MONAN-JEDI com simpleWorkflow

Execute a partir da raiz deste repositório:

```bash
simpleworkflow plan examples/simpleworkflow/3dfgat_mpastatic_x1.10242_2018041500/workflow.yaml
simpleworkflow run examples/simpleworkflow/3dfgat_mpastatic_x1.10242_2018041500/workflow.yaml \
  --workdir build/simpleworkflow/3dfgat_mpastatic_x1.10242_2018041500
```

O YAML apenas encadeia `validate-config`, `prepare-runtime`, `render-yaml`, `render-pbs`, `submit --wait` e `validate-run`.

`submit --wait` persiste o Job ID no runtime, evita submissão PBS duplicada em retomadas e espera apenas a conclusão no scheduler. A confirmação científica ocorre em `validate-run`, conforme o contrato declarado em `validation.yaml`.

Este exemplo é estático. A ciclagem temporal será habilitada quando as etapas de MPAS e Obs2IODA prepararem entradas e produtos específicos por ciclo.
