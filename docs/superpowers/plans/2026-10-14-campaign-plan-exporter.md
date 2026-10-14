# Campaign plan e exportador simpleWorkflow — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separar a descrição da campanha de sua exportação, reproduzindo o workflow validado da JACI sem alterar ciência ou execução.
**Architecture:** Três módulos pequenos: tipos/validação, definição das tarefas científicas e exportação simpleWorkflow. A API atual delega a eles; não há novo scheduler, executor ou CLI.
**Tech Stack:** Python >=3.10, dataclasses/enum/datetime da biblioteca padrão, PyYAML já instalado, pytest.
**Spec:** [Separação científica](../specs/2026-10-14-scientific-stage-separation-design.md).
**Execução proposta:** nesta sessão, pelo agente principal. Estado: plano para revisão; implementação ainda não iniciada.

## Global Constraints

- Preservar comandos legados prepare/submit/wait/validate e gates explícitos nesta entrega.
- Preservar IDs, dependências, argv, inputs/outputs e calendários da referência.
- 15 tarefas de inicialização, 17 por template e 11 no último ciclo: 502 estados em 29 análises.
- Nenhum download, submissão PBS, instalação científica, limpeza ou alteração de campanha durante construção/exportação.
- Sem dependências novas, renomeação, ecFlow, web ou mudança de inner/outer loops, B, física e malha.
- Configuração continua máquina/receita/experimento existente; não inferir parâmetros científicos de nomes de arquivo.
- A descrição comum representa um template por ciclo, independentemente do período.
- Manter compatibilidade das funções usadas por testes e consumidores do gerador atual.

## Review Focus

- Timezone, virada de mês/ano e ciclos não alinhados: normalizar UTC e recusar minutos/segundos ou intervalo inválido.
- Dependências de tarefas restritas ao penúltimo ciclo: não deixar tarefa ativa depender de tarefa ausente no ciclo final.
- Exportação repetida e estruturas mutáveis: produzir objetos novos, sem alterar plano ou exportações anteriores.
- Alias de timestamp e caminhos especiais: preservar paths com espaços; mapear somente tokens conhecidos e recusar formatos inválidos, sem shell.
- Recursos ainda gerenciados pelos comandos PBS: não inferir nem assumir que executor local é job concluído; a troca de dono PBS é posterior.

Cada foco é coberto pelos testes das tarefas 1–3 abaixo.

## Arquivos e fronteiras

| Arquivo | Responsabilidade |
|---|---|
| `monan_jedi_workflow/campaign_plan.py` | Tipos do plano, calendário e validação pura |
| `monan_jedi_workflow/campaign_definition.py` | Construir as tarefas científicas tipadas |
| `monan_jedi_workflow/exporters/__init__.py` | Namespace de exportadores |
| `monan_jedi_workflow/exporters/simpleworkflow.py` | Serializar o plano para o formato atual |
| `monan_jedi_workflow/corrected_campaign.py` | Delegar geração; conservar materialização/reparos existentes |
| `tests/test_campaign_plan.py` | Calendário, grafo, seleção e validações |
| `tests/test_simpleworkflow_exporter.py` | Referência JACI, isolamento e configuração real do motor |
| `docs/developer/campaign-plan.md` | Contratos e limites da primeira entrega |

A construção das tarefas sai de `corrected_campaign.py`; materialização, cópia de
cases, patches científicos e lançamentos em `campaign.py` ficam intactos.
Não manter duas versões da topologia após a extração.

## Task 1: Plano tipado e validação pura

**Files:** criar `campaign_plan.py` e `tests/test_campaign_plan.py`.

**Interfaces:**
- `CycleScope(str, Enum)`: `ALL='all'`, `NOT_LAST='not_last'`.
- `TaskSpec`: dataclass frozen com `name: str`, `argv: tuple[str, ...]`,
  `depends_on: tuple[str, ...] = ()`, `required_inputs: tuple[str, ...] = ()`,
  `required_outputs: tuple[str, ...] = ()`,
  `scope: CycleScope | None = None`, `input_fingerprint: str | None = None`.
  Scope omitido significa todos os ciclos; no exportador preserva a omissão atual.
- `CampaignPlan`: dataclass frozen com `schema_version: int`, `name: str`,
  `experiment_dir: str`, `start: datetime`, `end: datetime`,
  `step_hours: int`, `initialization: tuple[TaskSpec, ...]`,
  `tasks: tuple[TaskSpec, ...]`.
- `validate_plan(plan: CampaignPlan) -> None`: lança `StageConfigurationError`
  com tarefa/campo responsável. Não acessa filesystem nem importa motores.
- `analysis_times(plan: CampaignPlan) -> Iterator[datetime]`: UTC, inclusivo;
  valida calendário e usa geração incremental, sem materializar 1461 grafos.

Os recursos PBS já pertencem aos comandos legados e à configuração científica
existente. Nenhum schema de recursos novo será inventado nesta entrega. Quando
a submissão migrar, recursos explícitos serão acrescentados em uma entrega própria,
com schema versionado e testes do backend. `schema_version=1` identifica este
contrato mínimo, não o formato do simpleWorkflow.

- [ ] Escrever `test_inclusive_calendar`: 2/29/121/1461 análises em
  01/09 00Z→01/09 06Z, 08/09, 01/10 e 01/09 do ano seguinte.
- [ ] Escrever `test_invalid_calendar`: step <=0, bool como step, fim anterior,
  duração não múltipla, minutos/segundos e datetimes ingênuos em plano direto.
  O wrapper existente continua aceitando string sem timezone como UTC.
- [ ] Escrever `test_invalid_graph`: IDs duplicados/vazios, argv vazio,
  dependência ausente, autodependência e ciclo entre duas tarefas; IDs repetidos
  entre inicialização e tarefas cíclicas também são recusados.
- [ ] Escrever `test_scope_dependency_on_final_cycle`: tarefa ALL dependendo
  de NOT_LAST falha; NOT_LAST dependendo de ALL passa.
- [ ] Escrever `test_invalid_schema_and_scope`: versão desconhecida, selector
  diferente dos valores declarados e selector de ciclo na inicialização falham.
  Recusar tokens malformados/desconhecidos em argv/artefatos. Tokens genéricos
  permitidos: `experiment_dir`, `cycle_time`, `cycle_id`, `cycle_yyyymmddhh`,
  `cycle_year`, `cycle_month`, `cycle_day`, `cycle_hour`, `next_cycle_time`,
  `next_cycle_id`. O token científico `analysis_mpas_file_time` também é
  permitido antes da exportação; o antigo formato indexado fica somente no
  wrapper de reparo existente, não no plano novo. Paths não podem ser vazios.
- [ ] Executar `python -m pytest tests/test_campaign_plan.py -q` e confirmar falhas pelos novos tipos/contratos ausentes.
- [ ] Implementar tipos e validação, com DFS/topological traversal para o grafo.
  Aceitar somente fingerprints existentes `metadata`/`sha256` ou omissão.
- [ ] Reexecutar os testes até passar; commit `feat: add pure validated campaign plan`.

## Task 2: Definição científica e exportador equivalente

**Files:** criar `campaign_definition.py`, `exporters/__init__.py`,
`exporters/simpleworkflow.py` e `tests/test_simpleworkflow_exporter.py`.

**Interfaces:**
- `build_campaign_plan(*, start_cycle: str, end_cycle: str, experiment_dir: str,
  run_mpas_on_last_cycle: bool = False, cycle_interval_hours: int = 6,
  observation_outputs: list[str], analysis_output: str) -> CampaignPlan`.
- `build_initialization_tasks(start: datetime, step_hours: int) -> tuple[TaskSpec, ...]`.
- `build_cycle_tasks(*, run_mpas_on_last_cycle: bool,
  observation_outputs: list[str], analysis_output: str) -> tuple[TaskSpec, ...]`.
- `export_task(task: TaskSpec) -> dict[str, Any]`.
- `export_simpleworkflow(plan: CampaignPlan) -> dict[str, Any]`.
- `workflow_analysis_path(value: str) -> str`: move o mapper existente
  para o exportador; transforma o alias JEDI e o antigo formato indexado.

O builder cria `TaskSpec` diretamente; não desserializa YAML simpleWorkflow para
fingir independência. Preservar os tokens temporais genéricos já existentes.
O mapper de análise é aplicado às strings exportadas, sem mudar o plano.
O exportador sempre valida o plano, cria um documento novo e não escreve arquivo.
Nenhum exporter calcula FGAT, escolhe malha/física ou executa argv.

- [ ] Escrever `test_export_matches_jaci_reference`: comparar o dict completo
  com `docs/developer/evidence/20261014-jaci-reconciliation/workflow.yaml`,
  usando o experiment_dir da captura, outputs sondes/sfc/gnssro e target
  `Data/states/mpas.3dfgat.{analysis_mpas_file_time}.nc`.
- [ ] Escrever `test_forecast_on_last_cycle`: MPAS ALL quando configurado;
  publicação de background continua NOT_LAST em ambos os modos.
- [ ] Escrever `test_export_is_deterministic_and_isolated`: alterar o dict de
  uma exportação não muda o plano nem o resultado da próxima exportação.
- [ ] Escrever `test_export_has_no_side_effects`: negar subprocess/network,
  snapshot de arquivos temporários inalterado, nenhum qsub/swf invocado.
- [ ] Escrever `test_analysis_paths_for_utc_hours`: 00/06/12/18Z e virada de
  ano, paths com espaços, nenhum alias exclusivo JEDI/colchete em outputs.
- [ ] Escrever `test_structural_size_constant`: mesmos 32 IDs estruturais em
  2/29/121/1461 análises; opção final não muda a quantidade do template.
- [ ] Rodar os novos testes, confirmar falhas; extrair as construções existentes
  para os builders tipados e implementar serialização mínima.
- [ ] Passar os novos testes; commit `refactor: separate campaign definition from simpleWorkflow export`.

## Task 3: Compatibilidade e aceitação

**Files:** modificar `corrected_campaign.py`; criar `docs/developer/campaign-plan.md`;
atualizar os testes de integração existentes somente quando necessário.

**Interfaces:** `build_corrected_campaign_workflow` mantém assinatura/retorno
existentes, delegando a `build_campaign_plan` + `export_simpleworkflow`.
`_initialization_tasks`, `_cycle_tasks`, `_cycles`, `_parse_cycle`
e `_workflow_analysis_path` preservam os usos já existentes como wrappers
ou helpers delegados. Sem novo comando público.

- [ ] Escrever `test_legacy_builder_matches_exporter` e
  `test_legacy_initialization_helper`: chamadas antigas reproduzem os mesmos
  documentos/listas, inclusive inicialização seis horas antes de 01/09 00Z.
- [ ] Escrever `test_no_motor_import_in_domain`: os dois módulos de domínio
  não importam simpleworkflow/exporters/scheduler nem usam subprocess.
- [ ] Escrever `test_export_is_accepted_by_simpleworkflow`: usar versão real
  0.6.2 para carregar configuração e resolver argv e artefatos nos 29 ciclos.
  Pin de revisão do checkout de teste deve ser registrado; se indisponível,
  registrar bloqueio, não substituir por fake para alegar aceitação.
- [ ] Rodar os testes para confirmar falhas; trocar somente a geração por
  delegação, mantendo todos os reparos/materialização existentes.
- [ ] Rodar `python -m pytest tests/test_campaign_plan.py tests/test_simpleworkflow_exporter.py tests/test_corrected_campaign_workflow.py tests/test_campaign.py tests/test_arbitrary_campaign_dates.py -q`.
- [ ] Rodar `python -m pytest -q`; analisar falhas antes de ampliar escopo.
- [ ] Documentar o contrato mínimo, recursos ainda legados, invariantes,
  migração futura de PBS e limites da evidência científica.
- [ ] Comparar o diff final: nenhuma mudança de stages, templates científicos
  ou workflow original da campanha; commit `refactor: delegate legacy campaign API to validated plan`.
- [ ] Publicar branch/PR de implementação separado, com validação e limitações.
  Não mesclar nem orientar pull científico até concluir revisão da entrega.

## Aceitação e validação JACI

Conclusão local exige testes do domínio, igualdade completa com a referência,
aceitação pelo motor real e suíte do projeto. Não alegar sucesso científico.

A validação posterior usa novo diretório e um ciclo real, com build e insumos
rastreados. Não submeter automaticamente nem alterar a campanha concluída.
PBS, uniformização de runners e novas integrações terão planos próprios.

## Auto-revisão

- Escopo cobre somente a primeira entrega aprovada, não todos os alvos futuros.
- Interfaces consumidas nas tarefas 2/3 correspondem aos tipos da tarefa 1.
- Cinco focos de robustez têm testes definidos, sem testar detalhes de implementação.
- Referência de equivalência é arquivo capturado, não uma cópia do novo gerador.
- Recursos PBS não são ignorados: permanecem explicitamente sob o contrato legado.

