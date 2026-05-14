# Documentation site

## Selected tool

The web documentation uses **MkDocs**.

MkDocs was selected because the project already relies on Markdown, YAML and shell scripts. It is lightweight, easy to maintain and compatible with GitHub Pages.

## Local preview

```bash
python3 -m pip install -r requirements-docs.txt
mkdocs serve
```

Open:

```text
http://127.0.0.1:8000
```

## Build static site

```bash
mkdocs build
```

The output is written to:

```text
site/
```

## Future publication

The site can later be published through GitHub Pages using GitHub Actions. This PR prepares the documentation structure but does not enable automatic publishing.

## Bilingual organization

```text
docs-site/
├── index.md
├── pt/
└── en/
```

Each language has pages for overview, architecture, installation, usage, cookbook, extension, developers, users, troubleshooting and file reference.
