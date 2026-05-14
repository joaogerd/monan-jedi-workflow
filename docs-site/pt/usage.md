# Guia de uso

## Fluxo típico para um caso 3DVar-FGAT

O fluxo de uso atual é orientado ao primeiro caso 3DVar-FGAT no JACI.

```text
carregar ambiente
validar ambiente
criar árvore de dados
preparar dados externos
stagear arquivos
validar insumos
renderizar YAML JEDI
preparar runtime
gerar PBS
submeter job
```

## 1. Carregar ambiente

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
```

## 2. Validar runtime

```bash
bash scripts/setup/check_runtime.sh configs/sites/jaci/site.env
bash tests/smoke_check.sh
```

## 3. Criar diretórios de dados

```bash
bash scripts/setup/bootstrap_3dvar_fgat_data_layout.sh
bash scripts/setup/create_3dvar_fgat_external_tree.sh
```

## 4. Colocar arquivos reais em `MONAN_EXTERNAL_DATA_ROOT`

Estrutura esperada:

```text
${MONAN_EXTERNAL_DATA_ROOT}/
├── background/2024081500/
├── observations/ioda/2024081500/
├── covariance/
├── graph/
└── static/
```

## 5. Stagear dados

Primeiro faça um ensaio:

```bash
bash scripts/setup/stage_3dvar_fgat_inputs.sh --dry-run
```

Depois stageie de fato:

```bash
bash scripts/setup/stage_3dvar_fgat_inputs.sh
```

## 6. Validar insumos científicos

```bash
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh
bash scripts/setup/audit_3dvar_fgat_scientific_inputs.sh
```

Para IODA:

```bash
python3 tools/check_ioda_inventory.py \
  --inventory configs/experiments/3dvar_fgat/ioda_inventory.example.yaml \
  --manifest configs/experiments/3dvar_fgat/observers.yaml \
  --metadata configs/jedi/obs_plugs/variational/metadata.yaml \
  --strict-files
```

## 7. Renderizar configuração JEDI

```bash
bash scripts/run/render_3dvar_fgat.sh
```

Saídas esperadas:

```text
build/rendered/3dvar_fgat.yaml
build/rendered/observers.yaml
```

## 8. Preparar runtime

```bash
bash scripts/run/prepare_3dvar_fgat_runtime.sh --strict
```

## 9. Gerar job PBS

```bash
bash scripts/run/render_3dvar_fgat_pbs.sh
cat build/rendered/3dvar_fgat.pbs
```

## 10. Submeter no PBS

Somente após validação completa:

```bash
qsub build/rendered/3dvar_fgat.pbs
```

## Fluxo semanal de ciclos

Para uma semana com ciclos de 6 h, o sistema deve evoluir para gerar 28 ciclos. O conceito é:

```text
analysis(ciclo N) → forecast curto → background(ciclo N+1)
```

A implementação dessa ciclagem ainda deve ser adicionada em uma etapa futura.
