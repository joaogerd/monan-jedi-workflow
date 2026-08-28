# Templates do caso cíclico de referência

`variational.baseline_passed.yaml.in` foi derivado de:

```text
configs/experiments/3dfgat_mpastatic_x1.10242_2018041500/reference/baseline_passed.yaml
```

A regra de derivação é conservadora: preservar a configuração científica que passou e substituir somente itens que precisam variar por ciclo ou por diretório de runtime.

Foram parametrizados:

- início da janela;
- background filename/date;
- data da covariância, preservando a convenção do baseline;
- paths dos namelists/streams dentro do `run_dir`;
- data nos nomes das observações.

Não foram alterados:

- variáveis de modelo/análise;
- observers e operadores;
- filtros;
- minimizador;
- número de inner iterations;
- modelo de covariância.

Antes de uso científico, compare novamente este template com o **baseline atual que passa**. Se o baseline mudar, atualize primeiro a referência e depois este template de forma explícita/revisável.
