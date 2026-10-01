# Diagnóstico, status e restart

Antes de submeter:

```bash
monan-jedi-workflow campaign check campaign.yaml
```

Materialize sem executar:

```bash
monan-jedi-workflow campaign create campaign.yaml
swf plan cases/meu-experimento/workflow.yaml
```

Execute e consulte:

```bash
monan-jedi-workflow campaign run campaign.yaml
monan-jedi-workflow campaign status campaign.yaml
```

Se houver falha, não apague o caso. Inspecione o stage, seu log e o manifesto
de validação; depois retome pelo simpleWorkflow. Término do PBS não significa
sucesso científico: os stages de validação aceitam ou rejeitam cada produto.
