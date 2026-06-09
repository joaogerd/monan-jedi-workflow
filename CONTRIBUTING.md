# Contributing

Este repositório deve evoluir sempre em passos pequenos, revisáveis e testáveis. A prioridade é preservar a reprodutibilidade do baseline MPAS-JEDI antes de generalizar o workflow.

## Fluxo de desenvolvimento

1. Atualize a branch `main` local.
2. Crie uma branch curta e descritiva.
3. Faça uma mudança pequena por PR.
4. Rode os testes antes de abrir o PR.
5. Abra o PR contra `main`.
6. Faça merge somente depois que o CI passar.

Exemplo:

```bash
git switch main
git pull --ff-only
git switch -c docs/minha-mudanca
python -m pytest
```

## Testes

A suíte local deve ser executada com:

```bash
python -m pytest
```

O GitHub Actions executa os testes automaticamente em pull requests para `main` e em pushes para `main`, usando Python 3.10, 3.11 e 3.12.

## Configuração de experimentos

O baseline atual usa configuração dividida em arquivos YAML dentro de `configs/experiments/` e fragmentos reutilizáveis dentro de `configs/fragments/jedi/`.

Use seletores compactos nos experimentos quando a configuração for compartilhada:

```yaml
variables:
  use: mpas_3dfgat_core
```

```yaml
observations:
  use:
    - radiosonde
    - gnssro_ref_ncep
    - sfc_corrected
```

Evite duplicar listas longas de variáveis ou observadores dentro de cada experimento. Prefira criar ou reutilizar fragmentos versionados.

## Segurança operacional

Este workflow não deve submeter jobs automaticamente.

Comandos como `validate-config`, `render-yaml` e `render-pbs` são seguros porque apenas validam ou renderizam arquivos. Qualquer chamada a `qsub`, `mpiexec`, `mpirun` ou execução real do `mpasjedi_variational.x` deve ser uma ação manual e explícita.

## Dados e saídas

Não versione dados grandes, saídas de modelo, logs ou diretórios gerados. Em especial, não commite arquivos `*.nc`, `*.nc4`, `*.grib`, `*.bufr`, `build/`, `runtime/`, `scratch/` ou `logs/`.

## Estilo dos PRs

Prefira títulos no formato:

```text
tipo: descrição curta
```

Exemplos:

```text
config: add new observer fragment
test: cover rendered YAML structure
docs: document runtime preparation
ci: update pytest workflow
```

Mantenha o corpo do PR objetivo, com resumo, notas de segurança operacional e indicação clara do que foi ou não testado.
