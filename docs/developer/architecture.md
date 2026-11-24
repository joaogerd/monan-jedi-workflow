# Arquitetura implementada — MONAN-JEDI Workflow (beta 0.3.0b1)

Este documento descreve **a implementação verificável do branch `feat/platform-domain-apps`**, e não o desenho de uma versão futura. Para utilização, comece pelo [tutorial](../tutorial.md).

## Separação de responsabilidades

| Camada | Código/contrato atual | Responsabilidade |
| --- | --- | --- |
| CLI de entrada | `command_entrypoints.py`, `unified_cli.py` | `experiment create/check/export/validate/plan/run/status`, `diagnose` |
| Configuração de domínio | `platform_cli.py`, `platform_config.py`, `domain_cli.py` | Interpretar opções, YAMLs, horários e solicitações de uma operação |
| Campanha | `platform_campaign.py` | Validar calendário, expandir etapas e **exportar** o DAG em `workflow.yaml` |
| Orquestração | dependência externa `simpleWorkflow`, fixada em `pyproject.toml` | Agendar dependências, registrar estado, assinaturas, logs e retomada |
| Estágios científicos | `wps_stage.py`, `init_stage.py`, `obs2ioda_stage.py`, `jedi_stage.py`, `mpas_stage.py` e adaptadores | Preparar arquivos, submeter PBS nativo, aguardar e validar produtos |
| Diagnóstico operacional | `diagnostics.py` | Consultar dados persistidos e logs, explicar a falha principal **sem executar** a ciência |

A nomenclatura do projeto indica **MONAN-JEDI**, mas o baseline científico atual é MPAS-JEDI. Não registrar uma execução MPAS como prova de assimilação sobre o núcleo MONAN.

## Controle no login; ciência nos compute nodes

```text
Terminal do pesquisador (JACI login)
  -> experiment create
  -> campaign.yaml / experiment.yaml / science/*.yaml
  -> experiment check + export
  -> workflow.yaml
  -> experiment run
      -> simpleWorkflow
           -> aplicativo Python de domínio: prepare
           -> aplicativo Python de domínio: run
                -> PBS nativo: qsub + wait (shell e executável científico)
           -> aplicativo Python de domínio: validate
           -> próxima tarefa, apenas após sucesso
```

O `simpleWorkflow` emprega tarefas `executor: local` nesta integração. Isso **não** significa que o modelo rode no nó de login: a operação `run` dos aplicativos controla sua submissão PBS nativa. Requer binários, bibliotecas, scripts e diretórios científicos disponíveis em `/p` e nos compute nodes; o Python do controlador pode ficar no ambiente Conda do login.

## Exportação de ciclos: implementação atual

O exportador `monan_jedi_workflow/platform_campaign.py`:

1. Lê `schema_version: 1`, `experiment` e `calendar.start/end/interval`.
2. Calcula horários, respeitando `calendar.end_inclusive` (padrão atual: `true`).
3. Monta `initialization.tasks` executadas uma única vez.
4. **Expande o DAG por horário**, com nomes semelhantes a `c00004_obs_convert_prepare`, `c00004_jedi_run` e `c00004_mpas_validate`.
5. Exporta `workflow.yaml`, recusando substituir um arquivo existente.

Os nomes `c00000`, `c00001` etc. são derivados da posição no calendário. O calendário maior **gera mais tarefas estruturais**. O ADR 0005 descreve um projeto futuro de ciclos nativos com DAG estruturalmente constante; **a implementação atual não corresponde a esse ADR**. Trate-o como intenção de arquitetura, não como contrato de execução.

## Tempo e continuidade científica

O `cycle` do JEDI representa a **hora da análise**. Os deslocamentos de FGAT e os arquivos de estado dependem do método e são parametrizados na receita; não devem ser deduzidos do nome da pasta. A fase de inicialização fornece o primeiro estado, a análise JEDI usa as observações no ciclo correto e a previsão MPAS produz os produtos que alimentam a análise seguinte. Consulte os documentos científicos de [trajetória FGAT](3dfgat-background-trajectory.md), [modelo temporal](cycle-time-model.md) e [handoff](analysis-to-mpas-forecast-handoff.md).

A receita de referência gerada pelo `experiment create` possui **duas análises**. Ampliar `calendar.end` sozinho não gera backgrounds adicionais e não configura automaticamente as entradas observacionais de toda uma campanha longa. Para a receita MPAS da JACI, veja o [preparador institucional de 3 e 7 dias](https://github.com/GAD-DIMNT-CPTEC/monan-jedi-2026/tree/main/experiments/M3/platform-domain-apps).

## Identidade, proveniência e segurança de restart

O estado do orquestrador reside em `.simpleworkflow/state.sqlite3`; os registros das tentativas ficam em `.simpleworkflow/runs/`. A assinatura das tarefas inclui parâmetros e arquivos de entrada, além de atributos do executável e do ambiente (por exemplo, `PATH` e `PYTHONPATH`). Mudanças de instalação ou variáveis após uma rodada parcial podem marcar atividades `SUCCESS` como desatualizadas e causar nova execução.

Por isso, jamais apagar manifests, PBS ou resultados para “destravar” uma execução. Um retry só é seguro depois de validar tarefas concluídas, seus produtos e assinaturas. A proteção WPS impede `prepare` destrutivo sobre estado científico persistente, mas não substitui uma política completa de retomada do orquestrador.

O `diagnose` consulta o `simpleWorkflow` e logs/PBS de forma somente leitura. A mensagem `BLOCKED` indica dependentes da falha original, não múltiplas causas independentes.

## Testes e validação

- **Unitários:** `python -m pytest -q` em ambiente de desenvolvimento, com dependências instaladas.
- **Contratos artificiais:** `examples/beta/manual.sh`, não substituem a execução científica.
- **Integração JACI:** inicialização, conversões Obs2IODA, análises JEDI, previsões MPAS, integridade NetCDF e relação temporal correta.
- **Validação meteorológica:** convergência da função custo, O-B/O-A, QC, observações utilizadas, estabilidade de 3/7 dias e comparação com controles independentes.

A documentação histórica em `docs/validation/` e os ADRs preservados registram evidências/decisões **com escopo e data específicos**. Não prevalecem sobre o código atual nem devem ser usados como tutoriais alternativos.

## Onde implementar novas funcionalidades

Código científico deve permanecer independente de `simpleWorkflow`: **o orquestrador decide quando executar; o aplicativo decide como executar e validar sua ciência**. Alterações devem incluir testes para o comportamento novo, casos de erro e estabilidade dos produtos já existentes. Consulte [CONTRIBUTING](../../CONTRIBUTING.md).
