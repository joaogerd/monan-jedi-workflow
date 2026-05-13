# Documentação para desenvolvedores

## Organização do código

```text
configs/       YAMLs e configurações shell
docs/          documentação técnica histórica
docs-site/     documentação web MkDocs
jobs/          templates de submissão
scripts/       comandos de setup e execução
tests/         smoke tests estruturais
tools/         ferramentas Python
workflow/      tarefas e templates de orquestração
```

## Convenções

- scripts Bash devem usar `set -euo pipefail` quando executados diretamente;
- scripts que podem ser carregados com `source` devem preservar o estado do shell;
- ferramentas Python devem falhar com mensagens claras;
- arquivos reais de dados não devem ser versionados;
- exemplos devem terminar com `.example.yaml` quando não forem configuração operacional final.

## Fluxo de contribuição

```bash
git checkout main
git pull
git checkout -b feature/nome-da-mudanca
# editar arquivos
git add .
git commit -m "Descrição clara"
git push -u origin feature/nome-da-mudanca
```

Abra um Pull Request com:

- objetivo;
- arquivos alterados;
- validações executadas;
- riscos e limitações;
- próximos passos.

## Estratégia de branches

Use branches pequenas e específicas:

```text
feature/jaci-site-env
feature/ioda-inventory
feature/mpas-jedi-build-finder
feature/docs-web-portal
```

Evite misturar documentação, scripts e mudanças científicas no mesmo PR, a menos que seja necessário.

## Rastreabilidade

Toda mudança operacional importante deve ter:

- documentação;
- teste ou validação manual registrada;
- indicação clara de arquivos afetados;
- comentário no PR quando validada no JACI.
