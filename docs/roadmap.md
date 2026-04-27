# Technical Roadmap

| Fase | Objetivo | Ações principais | Arquivos afetados | Critério de conclusão | Prioridade |
|---|---|---|---|---|---|
| 1 | Criar base inicial | Criar repo `monan-jedi-workflow`, publicar bootstrap e branch de trabalho | GitHub repo | Repositório criado e bootstrap disponível na `main` | Alta |
| 2 | Auditar estrutura original | Mapear `Run.py`, `initialize/`, `bin/`, `config/`, `scenarios/` | `docs/upstream_audit.md` | Inventário arquitetural publicado | Alta |
| 3 | Mapear configurações upstream | Separar MPAS, JEDI, site, workflow e experimento | `docs/upstream_configuration_map.md` | Mapa de configuração publicado | Alta |
| 4 | Criar manifesto de importação | Definir o que será preservado, reescrito, adiado ou rejeitado | `configs/templates/import_manifest.yaml` | Manifesto revisado antes de copiar arquivos científicos | Alta |
| 5 | Documentar MPAS | Mapear namelists, streams, geovars, variables, mesh resources | `docs/mpas_configuration.md`, `configs/mpas/` | Arquivos críticos classificados | Alta |
| 6 | Documentar JEDI | Mapear variational, HofX, ObsPlugs, SABER/BUMP, observers | `docs/jedi_configuration.md`, `configs/jedi/` | Templates preservados e explicados | Alta |
| 7 | Limpar arquivos desnecessários | Isolar NCAR-specific paths e exemplos pesados | `configs/sites/ncar/`, `docs/` | Nada científico removido sem registro | Média |
| 8 | Separar camadas | Dividir config genérica, científica, site e experimento | `configs/` | Layout novo funcional | Alta |
| 9 | Migrar C-shell para Bash | Reescrever scripts por tarefa, com testes de equivalência | `scripts/`, `workflow/tasks/` | Bash task passa no mesmo teste do legado | Média |
| 10 | Simplificar configuração | Reduzir variáveis espalhadas e adotar YAML/env | `configs/`, `scripts/env/` | Um experimento mínimo configurável | Alta |
| 11 | Adaptar PBS/JACI | Criar env, global.cylc e PBS templates | `configs/sites/jaci/`, `jobs/pbs/` | Smoke test PBS passa no JACI | Alta |
| 12 | Preparar 3DVar-FGAT | Criar experimento mínimo com janela, background e IODA | `configs/experiments/3dvar_fgat/` | `mpasjedi_variational.x` roda 1 ciclo | Alta |
| 13 | Importar templates mínimos | Importar `3dvar.yaml`, obs plugs convencionais e MPAS variational/forecast templates | `configs/jedi/`, `configs/mpas/` | Primeiro conjunto científico rastreável e documentado | Alta |
| 14 | Validar no JACI | Executar checks de ambiente, PBS smoke test e dry-run Cylc | `configs/sites/jaci/`, `jobs/pbs/`, `workflow/cylc/` | Logs de validação registrados | Alta |
| 15 | Documentação mínima | Instalação, configuração, execução, troubleshooting | `README.md`, `docs/` | Novo usuário consegue preparar ambiente | Alta |
| 16 | Testes de sanidade | Validar shell, YAML, paths e comandos | `tests/` | `tests/smoke_check.sh` passa | Alta |
| 17 | Branch/commits/PR | Commits organizados e PR inicial | GitHub PR | PR aberto com descrição técnica | Alta |

## Current branch focus

Branch: `feature/import-upstream-mpas-workflow`

Immediate goal:

1. document the upstream architecture;
2. map MPAS/JEDI configuration files;
3. define controlled import policy;
4. prepare the JACI/PBS site contract;
5. prepare the 3DVar-FGAT experiment contract.

This branch does not yet import the full upstream source tree. That is intentional. Full import
without classification would bring NCAR/Derecho paths and C-shell coupling into the MONAN runtime
layer too early.
