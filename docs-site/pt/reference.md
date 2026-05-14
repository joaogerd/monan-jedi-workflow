# Referência dos arquivos

## Configurações principais

| Arquivo | Função |
|---|---|
| `configs/sites/jaci/site.env.example` | Exemplo de configuração do JACI |
| `configs/sites/jaci/modules.sh` | Carregamento de módulos e Anaconda no JACI |
| `configs/experiments/3dvar_fgat/experiment.yaml` | Configuração base do experimento |
| `configs/experiments/3dvar_fgat/input_sources.example.yaml` | Registro genérico de fontes reais |
| `configs/experiments/3dvar_fgat/input_sources.jaci.example.yaml` | Registro específico para JACI |
| `configs/experiments/3dvar_fgat/staging.example.yaml` | Manifesto genérico de staging |
| `configs/experiments/3dvar_fgat/staging.jaci.example.yaml` | Manifesto de staging específico do JACI |
| `configs/experiments/3dvar_fgat/scientific_input_checklist.yaml` | Checklist científica dos insumos |
| `configs/jedi/applications/3dvar_fgat.yaml` | Template JEDI 3DVar-FGAT |
| `configs/jedi/obs_plugs/variational/metadata.yaml` | Metadados dos observers |

## Scripts de setup

| Script | Função |
|---|---|
| `scripts/setup/check_runtime.sh` | Valida ambiente |
| `scripts/setup/bootstrap_3dvar_fgat_data_layout.sh` | Cria árvore interna de dados |
| `scripts/setup/create_3dvar_fgat_external_tree.sh` | Cria árvore externa de entrada |
| `scripts/setup/stage_3dvar_fgat_inputs.sh` | Linka/copia dados para `MONAN_DATA_ROOT` |
| `scripts/setup/validate_3dvar_fgat_staged_inputs.sh` | Valida dados stageados |
| `scripts/setup/find_mpas_jedi_build.sh` | Procura builds MPAS-JEDI |
| `scripts/setup/check_mpas_jedi_build.sh` | Valida build configurado |

## Scripts de execução

| Script | Função |
|---|---|
| `scripts/run/render_3dvar_fgat.sh` | Renderiza YAML JEDI |
| `scripts/run/prepare_3dvar_fgat_runtime.sh` | Prepara runtime |
| `scripts/run/render_3dvar_fgat_pbs.sh` | Gera job PBS |
| `scripts/run/run_3dvar_fgat_variational.sh` | Monta/executa comando variational |

## Ferramentas Python

As ferramentas em `tools/` implementam validação, auditoria, renderização e staging. Elas devem concentrar lógica reutilizável, mantendo os scripts Bash como wrappers de alto nível.
