# Resultado da reconciliação JACI — 14/10/2026

## Fonte e escopo

Pacote recebido: `reconciliation-20261014.HFRacu.tar.gz`.
SHA-256: `30144c0fa2aa33d9a6af44e1e4317345657247f0b35bda5432022b375abcf67a`.
Coleta: 14/10/2026 18:50:58 UTC (15:50:58 de Brasília).
Os **2.419 arquivos regulares** do arquivo interno conferem com todos os
checksums fornecidos; não houve arquivo ausente ou divergente nessa conferência.

O pacote contém configurações, scripts PBS, manifests científicos e metadados
das tentativas do simpleWorkflow. Produtos NetCDF/BUFR, executáveis, logs
completos e SQLite não vieram no pacote. A conferência abaixo é de evidências
registradas e consistência entre arquivos, não uma revalidação dos dados ausentes.

## Código e ambiente na coleta

| Item | Resultado |
|---|---|
| Branch JACI | `feature/2025-reference-case` |
| HEAD no momento da coleta | `f9b37019ed6b7a27bb9b99c714fb97f5e00b67a3` |
| Diferenças em arquivos rastreados | Patch de zero bytes |
| Conteúdo não rastreado | `experiments/`, tutorial, captura M3 e diretório da coleta |
| Python | 3.11.16 |
| monan-jedi-workflow | 0.2.0, instalação editável no checkout informado |
| simpleWorkflow | 0.6.2, instalação editável em `projects/simpleWorkflow` |
| NumPy / netCDF4 / PyYAML | 1.26.4 / 1.7.4 / 6.0.3 |

A diferença para `dc0ac5d` no repositório remoto é a padronização visual publicada
em 13/10. O resumo diagnóstico capturado é estruturalmente idêntico ao publicado.
A diferença não justifica regenerar a campanha ou atualizar a instalação antes
de preservar a referência.

HEAD e versões são o estado **na coleta**. A instalação editável de simpleWorkflow
não identifica seu commit; a proveniência histórica de código/build ainda não está
completa. Arquivos científicos materializados são não rastreados e foram conferidos
diretamente no pacote, sem interpretar patch vazio como ausência de ajustes locais.

## Conferência da execução registrada

| Evidência | Conferência |
|---|---:|
| Manifests JEDI com `valid=true` | 29/29 |
| Manifests Obs2IODA com `valid=true` | 29/29 |
| Previsões MPAS cíclicas com `valid=true` | 28/28 |
| Previsão inicial e MPAS init | 1/1 cada |
| Backgrounds com tempos T−3/T coerentes | 29/29 |
| Hash do estado-base copiado no JEDI igual ao publicado pelo background | 29/29 |
| Links MPAS apontando à análise JEDI do mesmo ciclo | 28/28 |
| Metadados de tentativas em `success`, retorno zero | 502/502 |
| IDs de tarefa/ciclo distintos nos metadados | 502 |
| Jobs PBS distintos com manifests | 59 |
| Registros `run.json` arquivados | 30 |

O intervalo científico é 01/09/2025 00Z → 08/09/2025 00Z, sem lacunas no calendário
de seis horas. Os metadados registram execução de 12/10/2026 21:09:42 a 22:02:58 UTC.
Há uma tentativa registrada por tarefa/ciclo na captura; isso não prova ausência
de tentativas anteriores fora dessa captura. Os 30 registros de run não são
interpretados como 30 reinícios manuais.

O workflow materializado foi comparado como estrutura YAML com a saída das
funções puras do gerador no código auditado: **igualdade completa**. Foram
preservados calendário, argv, seletores, dependências e inputs/outputs.
São 15 tarefas de inicialização, 17 no template de ciclo e 11 aplicáveis no
último ciclo: `15 + 28 × 17 + 11 = 502`.
O YAML capturado passa a ser referência para a primeira entrega do exportador.

Jobs que identificam a rodada:
- MPAS init: `674260.pbs-ha`;
- previsão inicial: `674262.pbs-ha`;
- primeira análise: `674264.pbs-ha`;
- última análise: `674397.pbs-ha`.

A [tabela dos 29 ciclos](evidence/20261014-jaci-reconciliation/cycles.csv)
associa ciclos, jobs JEDI/MPAS e validações. Os jobs antigos com falha no registro
de 11/10 pertencem a outro estado da investigação.

## Receita materializada

A mesma configuração foi encontrada nos 29 YAMLs JEDI:
**um outer loop**, **dez inner iterations**, DRPCG e
`gradient norm reduction: 1e-10`. O valor está escrito assim nos YAMLs;
não é uma medida de convergência atingida.

Todos os PBS JEDI e as 28 previsões cíclicas usam **128 processos**, launcher
`/opt/cray/pals/1.6/bin/mpiexec` e
`GFORTRAN_CONVERT_UNIT=big_endian:101-200`.
O nonlinear outer usa PT20M/1200 s e `config_len_disp=240000`.
A previsão externa usa 1200 s e a mesma suite `mesoscale_reference`.

O inner é diferente: 1800 s e `config_len_disp=480000`.
Esses valores pertencem ao namelist da geometria inner e não demonstram uma
inconsistência no passo do modelo nonlinear outer. Não serão equalizados
automaticamente pela refatoração; decisões científicas exigem análise separada.
A atualização SST permanece desabilitada na configuração outer/forecast.

As fontes registradas mantêm PREPNR e GPSRO. A sequência dos manifests é coerente:
cada forecast produz T+3/T+6 para o background seguinte, e sua validação
antecede a submissão da análise consumidora.

## Proveniência ainda incompleta

O manifesto `reference-provenance.json` preserva o hash do executável JEDI
na criação:
`07e993f128b60053602a4cf343bbaba71516cf9a0246fa2833d0661e358511df`.
Isso não prova que o binário permaneceu igual durante toda a execução.
O status `not scientifically validated` nesse manifesto é o registro de criação;
as validações posteriores dos ciclos são evidências distintas. Não alterar o
manifesto original para atualizar retroativamente seu significado.

Ainda faltam para reprodução completa:
- revisão Git e diferenças do checkout editável de simpleWorkflow;
- identidade/build e hashes dos demais executáveis e insumos fixos;
- confirmação de que o hash JEDI de criação corresponde às tentativas executadas;
- logs completos e conferência de seus hashes reais, além do resumo publicado;
- snapshot consistente do SQLite;
- cópia das pequenas configurações externas apontadas por links e perfis de origem.

A captura inventaria links; não prova que seus destinos existem hoje.
As validações JEDI do pacote registram marcadores de log e outputs, sem
revalidação NetCDF independente anexada. Não ampliar essa evidência para afirmar
qualidade das previsões ou validação científica mais forte que o contrato usado.

## Consequência para a arquitetura

A referência está suficientemente reconciliada em configuração/topologia para
definir e testar localmente a primeira entrega: descrição comum e exportador
simpleWorkflow equivalente. Não há divergência explicada pelo pacote que demande
reiniciar os sete dias ou corrigir seus arquivos automaticamente.

A captura não autoriza substituir PBS, parâmetros do minimizador ou malha nas
campanhas existentes. A nova execução real exige configuração/build rastreáveis,
diretório separado e comparação dos artefatos. ecFlow, renomeação e web seguem
posteriores aos contratos.

Próximo passo: revisar a [especificação](../superpowers/specs/2026-10-14-scientific-stage-separation-design.md)
e detalhar a primeira entrega usando o
[workflow capturado](evidence/20261014-jaci-reconciliation/workflow.yaml)
como referência de equivalência.

Resumo estruturado: [audit.json](evidence/20261014-jaci-reconciliation/audit.json).

