# Cookbook / How-to

Esta seção apresenta receitas práticas para tarefas comuns.

## Como configurar o sistema para um novo ambiente HPC

1. Crie um diretório em `configs/sites/<site>/`.
2. Adicione um `site.env.example`.
3. Defina módulos, filas, conta, paths e MPI launcher.
4. Crie um carregador de ambiente específico, se necessário.
5. Rode validações equivalentes a:

```bash
bash scripts/setup/check_runtime.sh configs/sites/<site>/site.env
```

Evite colocar paths de site dentro de arquivos científicos do JEDI ou do MONAN.

## Como adaptar uma configuração existente

Copie o exemplo antes de modificar:

```bash
cp configs/experiments/3dvar_fgat/input_sources.jaci.example.yaml \
   configs/experiments/3dvar_fgat/input_sources.jaci.yaml
```

Edite a cópia local e mantenha o exemplo versionado como referência.

## Como adicionar um novo observer

1. Crie um template em `configs/jedi/obs_plugs/variational/`.
2. Adicione a entrada em `configs/experiments/3dvar_fgat/observers.yaml`.
3. Adicione metadados em `configs/jedi/obs_plugs/variational/metadata.yaml`.
4. Atualize o inventário IODA.
5. Rode:

```bash
python3 tools/check_observer_manifest.py configs/experiments/3dvar_fgat/observers.yaml
python3 tools/check_observer_metadata.py \
  --manifest configs/experiments/3dvar_fgat/observers.yaml \
  --metadata configs/jedi/obs_plugs/variational/metadata.yaml
```

## Como modificar componentes sem quebrar a arquitetura

Antes de alterar um script, identifique sua camada:

- configuração de site;
- configuração científica;
- staging de dados;
- renderização;
- runtime;
- submissão PBS;
- orquestração.

Não misture responsabilidades. Um script de PBS não deve conter lógica científica. Um YAML JEDI não deve conter paths fixos do JACI.

## Como testar mudanças

Rode sempre:

```bash
bash tests/smoke_check.sh
```

Para alterações em dados:

```bash
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh --allow-missing
bash scripts/setup/check_3dvar_fgat_input_consistency.sh
```

Para alterações no build:

```bash
bash scripts/setup/check_mpas_jedi_build.sh
```

## Como depurar problemas comuns

### Python antigo no JACI

Sintoma:

```text
SyntaxError: future feature annotations is not defined
```

Solução:

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
```

Esse comando carrega Anaconda e `start_conda`.

### Arquivos IODA ausentes

Use:

```bash
python3 tools/check_ioda_inventory.py \
  --inventory configs/experiments/3dvar_fgat/ioda_inventory.example.yaml \
  --manifest configs/experiments/3dvar_fgat/observers.yaml \
  --metadata configs/jedi/obs_plugs/variational/metadata.yaml
```

### Build MPAS-JEDI ausente

Use:

```bash
bash scripts/setup/find_mpas_jedi_build.sh --max-depth 7 ${MONAN_JACI_WORKSPACE}/projects
```

## Como contribuir

1. Crie uma branch específica.
2. Faça commits pequenos.
3. Rode `bash tests/smoke_check.sh`.
4. Abra um Pull Request com descrição clara.
5. Documente decisões arquiteturais quando elas afetarem o uso futuro.
