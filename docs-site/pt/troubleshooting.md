# FAQ e solução de problemas

## `SyntaxError: future feature annotations is not defined`

Causa provável: Python antigo do sistema.

Solução:

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
```

Esse comando carrega Anaconda e usa o Python correto.

## `MONAN_EXTERNAL_DATA_ROOT is not set`

Causa: `site.env` local antigo ou variável não definida.

Solução:

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
echo $MONAN_EXTERNAL_DATA_ROOT
```

O carregador define um valor padrão quando possível.

## Arquivos IODA não encontrados

Use:

```bash
bash scripts/setup/check_external_input_root.sh --allow-missing
bash scripts/setup/stage_3dvar_fgat_inputs.sh --dry-run
```

Confirme se os arquivos existem em `MONAN_EXTERNAL_DATA_ROOT` antes do staging.

## Build MPAS-JEDI não encontrado

Use:

```bash
bash scripts/setup/find_mpas_jedi_build.sh --max-depth 7 ${MONAN_JACI_WORKSPACE}/projects
```

Quando encontrado, atualize `MPAS_BUNDLE_BUILD` no `site.env`.

## PBS gerado mas não deve ser submetido

Antes de `qsub`, rode:

```bash
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh
bash scripts/setup/check_mpas_jedi_build.sh --strict
bash scripts/run/prepare_3dvar_fgat_runtime.sh --strict
```

## Dados reais não devem entrar no Git

Arquivos NetCDF, HDF5, graph info e outputs devem ficar em áreas de dados, não versionados no repositório.
