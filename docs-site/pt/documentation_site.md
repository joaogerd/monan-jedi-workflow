# Site de documentação

## Ferramenta escolhida

A documentação web usa **MkDocs**.

A escolha foi feita porque o projeto já utiliza Markdown, YAML e scripts shell. O MkDocs é simples, leve, fácil de manter e compatível com GitHub Pages.

## Build local

```bash
python3 -m pip install -r requirements-docs.txt
mkdocs serve
```

Acesse:

```text
http://127.0.0.1:8000
```

## Gerar site estático

```bash
mkdocs build
```

A saída será criada em:

```text
site/
```

## Publicação futura

A publicação pode ser feita via GitHub Pages usando GitHub Actions. Esta PR prepara a estrutura, mas não ativa publicação automática.

## Organização bilíngue

```text
docs-site/
├── index.md
├── pt/
└── en/
```

Cada idioma possui páginas equivalentes para visão geral, arquitetura, instalação, uso, cookbook, extensão, desenvolvedores, usuários, troubleshooting e referência.
