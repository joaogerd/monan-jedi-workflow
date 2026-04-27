# Technical Roadmap

| Fase | Objetivo | Ações principais | Arquivos afetados | Critério de conclusão | Prioridade |
|---|---|---|---|---|---|
| 1 | Criar cópia/fork inicial | Criar repo `monan-jedi-workflow`, importar upstream e criar branch | GitHub repo | Repositório criado com histórico ou cópia rastreável | Alta |
| 2 | Auditar estrutura original | Mapear `Run.py`, `initialize/`, `bin/`, `config/`, `scenarios/` | `docs/migration_notes.md` | Inventário publicado | Alta |
| 3 | Documentar MPAS | Mapear namelists, streams, geovars, variables, mesh resources | `docs/mpas_configuration.md`, `configs/mpas/` | Arquivos críticos classificados | Alta |
| 4 | Documentar JEDI | Mapear variational, HofX, ObsPlugs, SABER/BUMP, observers | `docs/jedi_configuration.md`, `configs/jedi/` | Templates preservados e explicados | Alta |
| 5 | Limpar arquivos desnecessários | Isolar NCAR-specific paths e exemplos pesados | `configs/sites/ncar/`, `docs/` | Nada científico removido sem registro | Média |
| 6 | Separar camadas | Dividir config genérica, científica, site e experimento | `configs/` | Layout novo funcional | Alta |
| 7 | Migrar C-shell para Bash | Reescrever scripts por tarefa, com testes | `scripts/`, `workflow/tasks/` | Bash task passa no mesmo teste do legado | Média |
| 8 | Simplificar configuração | Reduzir variáveis espalhadas e adotar YAML/env | `configs/`, `scripts/env/` | Um experimento mínimo configurável | Alta |
| 9 | Adaptar PBS/JACI | Criar env, global.cylc e PBS templates | `configs/sites/jaci/`, `jobs/pbs/` | Smoke test PBS passa no JACI | Alta |
| 10 | Preparar 3DVar-FGAT | Criar experimento mínimo com janela, background e IODA | `configs/experiments/3dvar_fgat/` | `mpasjedi_variational.x` roda 1 ciclo | Alta |
| 11 | Documentação mínima | Instalação, configuração, execução, troubleshooting | `README.md`, `docs/` | Novo usuário consegue preparar ambiente | Alta |
| 12 | Testes de sanidade | Validar shell, YAML, paths e comandos | `tests/` | `tests/smoke_check.sh` passa | Alta |
| 13 | Branch/commits/PR | Commits organizados e PR inicial | GitHub PR | PR aberto com descrição técnica | Alta |
