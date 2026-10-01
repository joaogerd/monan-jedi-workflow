# Configuração das observações

O `obs2ioda.yaml` declara **de onde vêm as observações, como são convertidas e
quais arquivos IODA são produzidos**.

Comece por `examples/case/obs2ioda.yaml`.

```yaml
obs2ioda:
  variables: ...
  work_dir: ...
  runtime: ...
  inspection: ...
  provenance: ...
  converters:
    - name: ...
      inputs: [...]
      outputs: [...]
      argv: [...]
```

## Chaves

**variables** — caminhos e executáveis reutilizados pelos conversores.

**work_dir** — diretório de observações daquele ciclo. Deve variar com o ciclo.

**runtime.library_paths** — bibliotecas adicionais necessárias aos conversores.

**runtime.dependency_checks** — executáveis cujas dependências são verificadas
antes da conversão.

**inspection** — como o produto IODA será inspecionado e quais grupos/markers
devem existir.

**provenance.sha256** — registra hash dos produtos para rastreabilidade.

**converters** — lista declarativa. Cada conversor possui `name`, `inputs`,
`outputs` e `argv`. **A lista de outputs é a fonte de verdade das
observações da campanha**; o motor não contém nomes fixos como sondes ou
superfície.

Adicionar uma família observacional significa declarar seu produtor/output e
configurar o observer correspondente no JEDI. Não deve exigir alterar Python.
