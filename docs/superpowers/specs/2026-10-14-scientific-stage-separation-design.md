# Separação entre etapas científicas e orquestração

Data: 14/10/2026. Estado: proposta para revisão, ainda sem implementação.
Base de código inspecionada:
`dc0ac5d5a2343ddab646bb2c82f3ad133c31eb34` da branch
`feature/2025-reference-case`.

## Checkpoint de reconciliação recebido

A [captura JACI de 14/10](../../developer/2025-reference-reconciliation-result.md)
confirma configuração materializada, 29 ciclos e 502 metadados de tentativas.
O workflow capturado é idêntico à saída do gerador puro auditado e está
preservado como referência de equivalência. A primeira entrega pode ser
planejada/testada localmente após revisão desta especificação. A proveniência
histórica completa de builds, simpleWorkflow e dados segue necessária para
adoção e reprodução científica, conforme os limites do resultado da coleta.

## Objetivo e restrições acordados

Oferecer inicialização, OBS, JEDI e MPAS como etapas independentes com
prepara/roda/valida. Pesquisadores usam simpleWorkflow; a operação poderá usar
ecFlow. Ambos recebem dependências e recursos da mesma descrição da campanha.
As etapas recebem tempos explícitos, executam somente sua responsabilidade e
não avançam o calendário nem decidem lançar etapas seguintes.

A migração preserva a receita científica, os caminhos e produtos de referência
e a retomada da campanha existente. Aquisição ocorre para o ciclo/janela
solicitado; não há download global oculto em criação ou geração da campanha.
Um único responsável submete e acompanha cada job PBS. Configuração combina
máquina, receita científica e experimento, com sobrescritas explícitas.

A referência concluída é a campanha de 01–08/09/2025: 29 análises, 28 previsões
entre ciclos e 502 estados em sucesso. Ver
[reconciliação da referência](../../developer/2025-reference-reconciliation.md).
O ambiente efetivo e a associação histórica de arquivos ainda dependem da JACI.
Não se promete equivalência bit a bit com somente o pacote diagnóstico.

## Escolha da abordagem

| Abordagem | Benefício | Custo/risco |
|---|---|---|
| Descrição comum e exportador equivalente primeiro — recomendada | Isola a geração sem mudar execução científica ou dono atual de PBS | Os comandos submit/wait continuam provisoriamente |
| Uniformizar todos os runners e PBS primeiro | Atinge rapidamente a interface final | Muda simultaneamente execução, estado e retomada antes de comparar dependências |
| Migrar diretamente para ecFlow/mpaswf | Integração operacional antecipada | Mistura novos motores com a estabilização dos contratos e da referência |

A primeira entrega de código, após revisão e reconciliação, será uma
**descrição comum da campanha e um exportador simpleWorkflow equivalente**.
A interface prepara/roda/valida e a transferência do PBS são entregas posteriores,
cada uma com validação própria. ecFlow, renomeação e web ficam fora desta entrega.

## Inventário do código atual

Os caminhos abaixo são relativos à raiz do repositório auditado.

| Responsabilidade | Implementação atual | Fronteira a estabelecer |
|---|---|---|
| Ler campanha/preflight/materializar | `campaign.py`: `load_campaign_spec`, `preflight_campaign`, `materialize_campaign` | Separar descrição científica, geração e atalhos de execução |
| Gerar YAML simpleWorkflow | `corrected_campaign.py`: `build_corrected_campaign_workflow`, `_initialization_tasks`, `_cycle_tasks` | A topologia pertence à descrição comum; o formato ao exportador |
| Lançar/status/TUI de campanha | `campaign.py`: `_swf`, `run_campaign`, `status_campaign`, `tui_campaign` | Adaptador simpleWorkflow; nenhum import pelo núcleo científico |
| WPS e GFS inicial | `wps_stage.py`: `prepare_wps` chama `acquire_wps_input` | Suboperações da inicialização, com aquisição explícita no lifecycle futuro |
| Inicializar MPAS | `init_stage.py`: prepare/submit/wait/validate | Preparar e executar init; dono PBS no adaptador futuro |
| Aquisição de observações | `obs_cycle_stage.py`: `doctor_obs2ioda_resolved` chama aquisição | Doctor futuro somente inspeciona; execução OBS adquire/converte |
| Conversão/QC IODA | `obs2ioda_stage.py`: prepare/run/validate | Preservar conversores, seleção de fontes e contratos |
| JEDI | `jedi_stage.py`: prepare/submit/wait/validate | Runner científico síncrono separado de submissão/espera |
| Previsão MPAS | `mpas_stage.py`: prepare/submit/wait/validate | Mesmo princípio, preservando forecast/restart/streams |
| PBS | qsub em `jedi_stage.py`, `mpas_stage.py`, `init_stage.py`, `scheduler.py` | Um adaptador por execução, sem submissão dupla |
| Publicar/verificar background | `background_stage.py`: `publish_background`, `check_background` | Transformação com source/target explícitos; não avança calendário |

O inventário não comprova que todos os caminhos PBS são utilizados pela campanha:
distinguir chamadas realmente executadas de suporte legado antes de remover código.
Não há dependência `mpaswf` declarada no `pyproject.toml` inspecionado;
reutilização futura exige auditar sua API, versão e contratos separadamente.

Há efeitos relevantes para retomada: `prepare_mpas` limpa padrões declarados e
reescreve seu manifesto; `prepare_jedi` reescreve o manifesto de submissão;
`_repair_manifest` de OBS modifica o plano fora do estado validado.
A uniformização futura precisa proteger produtos e tentativas compatíveis.
A entrega de exportação não altera esses comportamentos.

## Contratos científicos finais

| Etapa | Entradas/tempo | Prepara | Roda | Valida/publica |
|---|---|---|---|---|
| Inicialização | Fonte externa declarada ou background pronto explicitamente validado; horários de origem e primeira análise | Plano GFS/WPS/init/forecast e configuração resolvida | Adquirir somente insumos necessários e executar suboperações declaradas | Primeiro estado de trajetória em T−3 e estado completo em T |
| OBS | Fontes e janela do ciclo de análise T | Plano de fontes, conversores, outputs e ambiente | Reutilizar dados compatíveis; adquirir ausentes; converter para IODA | Estrutura, variáveis, tempos e tratamento declarado de observador vazio |
| JEDI | IODA, B, geometria, estado T−3 e estado completo T | Runtime outer/inner e saída inicializada com o estado T | Executar aplicação JEDI do plano resolvido | Logs, análise e contratos NetCDF/tempos; manifesto de artefatos |
| MPAS | Análise validada em T e receita de previsão | Namelist, streams, partições, tabelas e outputs requeridos | Executar previsão até o horizonte declarado | Estado em T+3 e T+6 para próxima análise; prazos extras quando declarados |

A falta de um background intermediário é falha; não autoriza cold start.
O cenário de entrada com background pronto será representado explicitamente,
sem enfraquecer o caso validado com inicialização independente.

Para FGAT, trajetória inicial e estado-base da análise são artefatos diferentes.
A receita x1.10242 usa `model.tstep=PT20M` e `config_dt=1200`; a igualdade
temporal é uma regra de consistência. **Esses valores e a malha não são defaults
universais**: outra resolução deve fornecer sua própria receita compatível.
Outer/inner permanecem distintos; física da trajetória outer e da previsão
externa deve ser conferida. PREPNR não é substituído silenciosamente por PREP48H.
Inner/outer loops, B e atualização SST não mudam durante a migração arquitetural.

Publicação do próximo background recebe origem e destino fornecidos pelo plano.
Ela normaliza artefatos do produtor; não inicia MPAS/JEDI nem escolhe outro ciclo.

## Descrição comum e exportadores — primeira entrega

O núcleo do plano contém versão do schema, experimento, calendário inclusivo,
fase de inicialização, tarefas por ciclo, dependências, seletores de ciclo,
comandos em argv, inputs/outputs e recursos declarados. As unidades temporais e
os papéis de artefatos vêm do domínio.

Seletores semânticos necessários: todos os ciclos e todos exceto o último;
previsão no último ciclo segue a opção científica existente.
O plano representa o template de um ciclo, sem duplicar tarefas por data.
Um validador rejeita IDs repetidos, dependências ausentes, ciclos no grafo,
calendário incompatível e seletores inválidos.

O núcleo não contém `format_version` do simpleWorkflow, `cycle_scope`
do motor, chamadas a `swf`, scripts ecFlow ou estado de filas.
Os exportadores mapeiam seletores, variáveis e sintaxe; não recalculam janela
FGAT, física, background ou conjunto observacional.

Nesta primeira entrega, o exportador conserva os comandos legados
prepare/submit/wait/validate e gates explícitos. A migração dessas interfaces
não é condição para provar equivalência da topologia.

Compatibilidade exigida para a referência:
- 15 tarefas de inicialização e 17 tarefas do template de ciclo;
- 11 tarefas aplicáveis no ciclo final sem forecast adicional;
- 502 estados aplicáveis em 29 ciclos: `15 + 28 × 17 + 11`;
- mesmos IDs, argv resolvidos, dependências, inputs e outputs;
- timestamps 00/06/12/18Z aceitos pelo validador real do simpleWorkflow,
  sem variável específica de JEDI ou colchetes tratados como glob;
- nenhuma regeneração ou reparo automático de campanha existente por exportação.

O calendário enumera instâncias para verificação; o tamanho estrutural do YAML
permanece constante para 7, 30 e 365 dias.

## PBS e execução manual — direção da entrega posterior

Alvo: o adaptador de execução submete e monitora; o comando científico roda
sincronamente dentro da alocação. Execução manual usa o mesmo runner no ambiente
apropriado, ou um adaptador PBS explícito. Nenhum runner chama qsub/qstat.

No modo legado, os comandos atuais continuam sendo os únicos donos PBS.
No modo novo, o adaptador é o único dono. A seleção é explícita por execução
e não pode misturar os dois modos para a mesma tarefa.
A troca de dono requer testes de falha, retomada e submissão duplicada;
não se presume que a versão instalada do simpleWorkflow já suporte tudo isso.

## Proveniência, estado e erros

Manifesto científico: entradas/saídas por papel, ciclos e valid times, hashes,
malha/níveis, configuração efetiva, executáveis/builds, validações e logs.
Estado operacional: tentativas, job ID, fila, submissão, retorno e transições.
A associação usa ID de execução/tarefa; o estado operacional não decide sozinho
se um produto científico é consumível.

Compatibilidade para reuso considera configuração efetiva, entradas, executable
e contrato de outputs, não somente existência/tamanho. Sobreposição com execução
ativa é recusada; repetir etapa não apaga produtos válidos ou histórico sem ação
explícita. Transferências interrompidas não publicam arquivo parcial como pronto.

Sucesso exige o contrato solicitado. Erros devem conter etapa/ciclo, classe
(configuração/entrada/execução/validação), esperado/encontrado, arquivo responsável,
log e correção possível. Preservar códigos não zero; filas encerradas ou processo
com retorno zero não substituem validação científica.

Configuração resolve máquina → receita → experimento. Uma mesma chave pode ser
sobrescrita somente com precedência documentada e origem registrada. O snapshot
resolvido acompanha cada tentativa. Segredos de aquisição não integram manifests.

## Aceitação e sequência

1. Reconciliar a instalação JACI e a referência concluída; arquivar diferenças.
2. Aprovar esta especificação e produzir o plano detalhado da primeira entrega.
3. Implementar núcleo do plano/exportador; comparar com o gerador atual.
4. Verificar 2, 29, 121 e 1461 instâncias de análise, ciclos 00/06/12/18Z,
   dependências equivalentes e caminhos aceitos pelo motor real.
5. Executar comandos com processos simulados; confirmar ausência de download,
   qsub, limpeza ou alteração da campanha durante geração.
6. Só então validar um ciclo real em diretório separado antes de adoção.
7. Em especificação própria, extrair runners e PBS, separar manifestos,
   uniformizar lifecycle e testar retomada científica/operacional.
8. Depois avaliar integração mpaswf, ecFlow, renomeação e web.

Critério de parada: divergência de entradas/configuração, topologia ou produtos
em relação à referência sem explicação. Conservar a interface antiga até haver
evidência suficiente de equivalência. Testes locais não substituem validação JACI.

## Relação com a documentação existente

[Contratos atuais](../../developer/stage-contracts.md) e
[portabilidade](../../developer/orchestrator-portability.md) descrevem a interface
legada com submit/wait. Continuam válidos enquanto ela estiver em uso.
Esta proposta delimita a migração futura; não anuncia que a nova API já existe.

[ADR 0005](../../developer/adr/0005-native-cycle-campaigns.md) permanece referência
para os ciclos nativos atuais. A regra ali que restringe o primeiro background
à inicialização será revisada em entrega posterior para permitir entrada pronta
explicitamente validada. Nada muda no cold start do caso concluído.

