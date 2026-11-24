# Auditoria e consolidação documental — 23/11/2026

**Repositório:** `joaogerd/monan-jedi-workflow`  
**Branch:** `feat/platform-domain-apps`  
**Objetivo:** remover instruções obsoletas antes da integração em `develop`, tomando `docs/tutorial.md` como porta de entrada e confrontando os contratos públicos com o código presente no branch.

> Este relatório registra uma **auditoria estática e uma reorganização já aplicadas ao GitHub**, não um certificado de execução da JACI. Os testes automatizados e a validação científica continuam sendo portões independentes.

## Método e abrangência

1. O inventário foi obtido a partir da árvore recursiva do branch no GitHub (208 arquivos versionados no início desta auditoria).
2. Foram identificados os arquivos Markdown distribuídos em raiz, `.github`, `docs/`, documentação de desenvolvedores, validação, exemplos e catálogo.
3. Os conteúdos dos guias principais e os contratos críticos foram confrontados com `pyproject.toml`, `command_entrypoints.py`, `unified_cli.py`, `platform_campaign.py`, `experiment_start.py`, `obs_cycle_inputs.py`, `diagnostics.py`, com os YAMLs de `examples/case` e do catálogo de referência.
4. As referências Markdown locais dos documentos restantes foram examinadas contra a árvore de arquivos do branch após as exclusões; não foram encontrados destinos locais ausentes nessa conferência.
5. Foi criado `scripts/check_docs_links.py` para repetir essa verificação local de modo automatizável. A execução desse script por checkout ou CI ainda precisa ser confirmada; verificação de URLs externas não faz parte dele.

**Escopo:** documentação do repositório, não revisão de correção científica do software. O conteúdo de evidência histórica foi mantido com seu escopo original.

## Contradições identificadas no conjunto anterior

| Documento ou padrão anterior | Incompatibilidade observada | Tratamento |
| --- | --- | --- |
| `docs/configuration/campaign.md` | Ensinava `campaign.duration`, `profile` e `execution.swf_command`; `platform_campaign.py` usa `schema_version: 1`, `experiment`, `calendar`, `operations` e `output`. | **Reescrito** com schema da plataforma atual |
| `docs/troubleshooting.md` | Recomendava `monan-jedi-workflow campaign create/run/status` como rotina principal. | Removido; substituído por `diagnose` e pelo tutorial |
| `README.md`, `docs/first-experiment.md` | Duplicavam caminhos de onboarding e usavam `python -m monan_jedi_workflow.experiment_start` como entrada principal. | README reescrito; tutorial como referência; guia duplicado removido |
| `docs/developer/domain-cli-contract.md` | Afirmava que executáveis independentes ainda não estavam instalados; `pyproject.toml` e `command_entrypoints.py` já os declaram. | Removido |
| `docs/architecture.md` | Descrevia a arquitetura anterior usando somente um caso histórico de 2018. | Substituído por `docs/developer/architecture.md` verificado contra a plataforma atual |
| `docs/developer/adr/0005-native-cycle-campaigns.md` | Descrevia DAG estruturalmente constante, enquanto `platform_campaign.py` ainda expande tarefas `c00000`, `c00001` etc. | Mantido como **proposta futura ainda não implementada**, não como contrato operacional |
| `docs/validation/run-short-pilot.md` | Roteiro de empacotamento/piloto histórico, inadequado para o onboarding atual. | Removido; contexto histórico explicitado no relatório de 2025 |
| Planos em `docs/superpowers/` | Eram planos de implementação e proposta pré-entrega, com interfaces pretendidas não necessariamente implementadas. | Removidos do conjunto ativo; histórico disponível no Git |
| `docs/beta-testing.md` | Sobrepunha-se ao tutorial e misturava teste artificial com roteiro de instalação. | Removido; fixture permanece em `examples/beta/manual.sh` |
| `docs/unified-cli.md` | Duplicava as instruções de CLI do README/tutorial, com exemplos específicos de usuário. | Removido; CLI documentada na referência única |

## Arquivos excluídos do conjunto ativo

Os 15 caminhos removidos permanecem recuperáveis no histórico Git:

```text
docs/architecture.md
docs/troubleshooting.md
docs/unified-cli.md
docs/first-experiment.md
docs/beta-testing.md
docs/developer/domain-cli-contract.md
docs/developer/orchestration.md
docs/developer/orchestrator-portability.md
docs/developer/reference-cycle-model.md
docs/developer/jaci-validation-plan.md
docs/validation/run-short-pilot.md
docs/independent-date-validation.md
docs/superpowers/plans/2026-10-16-domain-cli-contract.md
docs/superpowers/plans/2026-10-16-platform-beta.md
docs/superpowers/specs/2026-10-16-platform-domain-apps-design.md
```

As decisões científicas e de arquitetura que ainda têm relevância foram preservadas nos ADRs e documentos técnicos atuais. O propósito desta limpeza não é eliminar evidência histórica, mas impedir que documentação de outra versão seja apresentada como instrução vigente.

## Organização documental de referência

| Público / finalidade | Fonte principal |
| --- | --- |
| Visão geral e ponto de entrada | [README](../README.md) |
| Aprender a usar, do zero até diagnóstico | [Tutorial](tutorial.md) — **único roteiro operacional canônico** |
| Sintaxe atual das campanhas | [Configuração da campanha](configuration/campaign.md) |
| Detalhamento de JEDI, MPAS e observações | `configuration/jedi.md`, `configuration/mpas.md`, `configuration/observations.md` |
| Erros e diagnóstico | [Diagnóstico](diagnostics.md) |
| Ambiente persistente na JACI | [Perfil do site](persistent-site-environment.md) |
| Arquitetura de implementação para desenvolvedores | [Arquitetura](developer/architecture.md) |
| Contratos e considerações científicas de desenvolvimento | `developer/stage-contracts.md`, `developer/cycle-time-model.md`, `developer/3dfgat-background-trajectory.md`, `developer/analysis-to-mpas-forecast-handoff.md` |
| Decisões e seus estados | [ADRs](developer/adr/README.md) |
| Evidência científica de versões/datas específicas | `validation/2025-reference-scientific-validation.md` e auditoria de regressão |
| Políticas de colaboração | [CONTRIBUTING](../CONTRIBUTING.md) e `developer/documentation-policy.md` |

Os arquivos em `examples/`, `monan_jedi_workflow/catalog/smoke/` e `monan_jedi_workflow/recipes/` integram os artefatos de referência, mas **não** devem ser confundidos com defaults científicos universais. Os exemplos com `EDITAR` são templates incompletos.

## Situação após revisão de 24/11/2026

- [x] Tutorial e README corrigidos para refletir a campanha independente de 29 ciclos na JACI.
- [x] Referências obsoletas ao preflight limitado a dois ciclos e ao preparador externo como caminho principal removidas.
- [x] Figuras científicas e relatório institucional vinculados à documentação operacional.
- [x] Verificação de links Markdown, testes Python e empacotamento incluídos na CI do branch.
- [ ] Validação independente de previsão, perfis de resolução alternativos e warm start ainda não demonstrados; são requisitos científicos futuros, não evidência do baseline MPAS de 240 km.
- [ ] Verificação de retomada segura após interrupção real e mudanças de ambiente permanece pendente.
- [ ] O branch `develop` ainda não existia no repositório no momento desta auditoria; há PR #72 em draft contra `main`.

A documentação histórica abaixo registra o estado em 23/11/2026 e **não substitui** este resumo posterior.

## Portões registrados na auditoria de 23/11/2026 (estado histórico)

- [ ] Executar `python scripts/check_docs_links.py` num checkout limpo do branch e corrigir qualquer quebra encontrada.
- [ ] Executar `python -m pytest -q` com o ambiente de dependências instalado e registrar versões/resultados.
- [ ] Conferir cada comando do tutorial com `--help` dos entrypoints da distribuição instalada.
- [ ] Confirmar instalação limpa **fora do checkout** e carregamento de `catalog:smoke` e do alias legado `catalog:reference-20250901`.
- [ ] Completar e avaliar campanhas independentes de 3 e 7 dias na JACI, sem reexecução destrutiva de etapas validadas.
- [ ] Verificar a retomada segura do `simpleWorkflow` quando `PATH`, `PYTHONPATH` ou atributos do executável mudam.
- [ ] Corrigir a seleção `swf explain --task` na fase de inicialização, se esse comportamento continuar reproduzível.
- [ ] Generalizar ou limitar explicitamente o `experiment check-inputs` (atualmente cobre somente dois ciclos) antes de anunciá-lo como preflight de campanhas longas.
- [ ] Reavaliar se o ADR 0005 será implementado ou substituído por nova decisão documentada antes da release.
- [ ] Após estabilização do branch, repetir a auditoria documental contra o código **do commit proposto para merge**, e não apenas contra o estado inicial desta revisão.

**Conclusão:** a documentação operacional conflitante foi reduzida e o caminho de aprendizado foi consolidado. Isso **não** comprova ainda prontidão para merge nem equivalência científica dos experimentos; as validações acima precisam de evidências próprias.
