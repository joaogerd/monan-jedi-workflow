# Retomada da arquitetura científica — 14/10/2026

## Estado reconciliado em 14/10/2026 — leitura prioritária

A campanha `monan-jedi-20250901-7d` foi concluída segundo o operador em
12/10/2026 e teve suas evidências publicadas em 13/10/2026:
**01/09/2025 00Z → 08/09/2025 00Z; 29 análises JEDI, 28 previsões entre
ciclos, 29 conversões Obs2IODA e 502/502 estados de tarefas em sucesso**.
A integração inicial é adicional às 28 previsões entre análises.

Fontes:
- [Relatório dos sete dias de 2025](https://github.com/GAD-DIMNT-CPTEC/monan-jedi-2026/blob/main/docs/relatorios/M3_7dias_2025-09.md).
- [Resumo extraído da campanha](https://github.com/GAD-DIMNT-CPTEC/monan-jedi-2026/blob/main/experiments/M3/2025-09-01-7dias/diagnostics/diagnostic_summary.json).
- [Proveniência e limites da captura](https://github.com/GAD-DIMNT-CPTEC/monan-jedi-2026/blob/main/experiments/M3/2025-09-01-7dias/provenance.json).

As tabelas registram dez iterações internas por ciclo, redução média de J de
28,03% e redução de 8,75% na média dos RMSEs de temperatura de radiossondas.
Isso sustenta continuidade e ajuste às observações assimiladas; não constitui
verificação independente da previsão nem critério para mudar o minimizador.

A reconstrução do runtime em `09a5ecba00a534e10cc347c2bbf853f93dbe5c3d`
preserva **128 processos JEDI**, endian GNU e namelists outer/inner distintos.
O valor JEDI=64 abaixo pertence ao estado histórico de 11/10.
128 é a configuração publicada da referência reconstruída; os PBS efetivos
de cada ciclo devem confirmar o que foi executado na JACI.

Histórico publicado inspecionado:
- `09a5ecb` (12/10): runtime reconstruído a partir da captura M3;
- `ede2ae1` e `7ff45bf` (12/10): caminhos de análise corrigidos na retomada;
- `f9b3701` (12/10): extração de diagnósticos das campanhas concluídas;
- `dc0ac5d5a2343ddab646bb2c82f3ad133c31eb34` (13/10): padrão visual M3,
  sem alteração das tabelas ou cálculos.

O último commit é a base desta inspeção de código, **não uma prova de que
a instalação científica executou exatamente esse commit**. O pacote publicado
não contém o estado Git completo da JACI, o SQLite, todos os logs nem as
configurações resolvidas. IDs dos jobs da rodada concluída e versões instaladas
ainda precisam ser coletados. Os jobs com falha registrados em 11/10 não podem
ser atribuídos automaticamente ao case reconstruído e concluído.

Diretório de referência:
```text
/p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow/experiments/2025-reference/cases/monan-jedi-20250901-7d
```

**Próxima ação:** seguir o [procedimento de reconciliação](developer/2025-reference-reconciliation.md),
preservar produtos e estado operacional, e revisar a
[especificação da separação científica](superpowers/specs/2026-10-14-scientific-stage-separation-design.md).
A reconciliação documental foi feita; a captura efetiva da JACI ainda não foi
recebida. A migração arquitetural não foi implementada.

Os checkpoints abaixo são históricos. Seus comandos de correção, download
ou reset não são instruções atuais para a campanha concluída.

## Registro histórico de 11–12/10/2026

Registro de decisão em 11/10/2026. Apresentação em terça-feira, 13/10; retomada em quarta-feira, 14/10. Este documento registra decisões e pendências, não uma migração concluída.

## Objetivo imediato e estado conhecido

Prioridade: executar a campanha de 7 dias, 01/09/2025 00Z a 08/09/2025 00Z, 29 análises, 28 previsões cíclicas e uma inicialização. Depois, campanha de 30 dias.
Repositório: joaogerd/monan-jedi-workflow; branch feature/2025-reference-case.
Referência científica: GAD-DIMNT-CPTEC/monan-jedi-2026, experiments/M3/3dias. Preservar ciência; não reutilizar datas/dados dinâmicos de 2018.
Malha x1.10242 (~240 km), 55 níveis; MPAS 128 ranks, JEDI 64; 3D-FGAT.
As observações PREPNR e GPSRO dos 29 ciclos foram adquiridas pelo pesquisador. Não substituir PREPNR por PREP48H silenciosamente.
No JACI, a campanha foi materializada e parou em wps_prepare: GFS de 2025083118 ausente. Não há confirmação de um ciclo científico completo.
A cópia recursiva de cases foi corrigida; 148 testes locais passaram naquele ponto. Isso não comprova execução científica no JACI.
Dados compartilhados: /p/projetos/monan_das/share/MONAN-JEDI-Data; B em covariance/x1.10242_240km/55levels; física em physics/mpas/files.
A configuração pessoal e o diretório materializado no JACI são a fonte dos ajustes locais; preservar ambos.

## Acordo arquitetural

O sistema científico define experimentos e oferece etapas delimitadas; o orquestrador controla sua execução.
Etapas: inicialização (quando necessária), OBS, JEDI e MPAS; interface comum prepara/roda/valida.
Preparação configura diretórios, parâmetros, fontes e execução. Execução realiza aquisição/processamento. Validação verifica os produtos necessários à próxima etapa.
OBS reutiliza dados locais válidos, adquire ausentes para o ciclo/janela e converte para IODA.
JEDI consome IODA, B e background/ trajetória validada; produz análise.
MPAS consome análise e produz previsão/restart e background/ trajetória do ciclo seguinte.
Primeiro background vem de inicialização ou entrada existente explicitamente validada. Falta de background no meio da campanha não autoriza cold start automático.

### Responsabilidades

- simpleWorkflow: orquestrador padrão dos pesquisadores; tarefas, dependências, ciclos, tentativas, retomada, monitoramento.
- ecFlow: integração futura para operação INPE; outros centros podem usar outros motores.
- monan-jedi-workflow (nome provisório): configuração científica, comandos de etapas, descrição da campanha e exportação para orquestradores.
- mpaswf: aproveitar capacidades de aquisição/preparação/inicialização/previsão; sua interface atual de pares NMC f024/f048 não deve ser usada cegamente como ciclo de assimilação.
- MONAN-JEDI: instalação executável e contrato de ambiente.
- MONAN-JEDI-Data: catálogo e insumos científicos compartilhados.

Etapas não importam motores de orquestração, avançam ciclos nem iniciam outras etapas por decisão própria.
Estado operacional pertence ao orquestrador; manifestos científicos registram entradas, saídas, versões e validações.
Exportadores traduzem uma descrição comum de tarefas/dependências/recursos para simpleWorkflow, ecFlow etc. Não duplicam decisões científicas.
Escolher um único responsável por submissão/monitoramento de cada job. Direção futura: orquestrador/adaptador submete; comando científico executa dentro do job.
Configuração: perfil de máquina + receita científica versionada + arquivo curto do experimento; preservar configuração efetiva e permitir sobrescritas explícitas.
Interface web futura usa os mesmos contratos, configurações e resultados, sem segundo caminho de execução.

## Trabalho de urgência antes da apresentação

Completar aquisição GFS na inicialização; retirar aquisição global implícita de create/run; adquirir OBS por ciclo; adaptar preflight para fontes declaradas.
Preservar provisoriamente os comandos prepare/submit/wait/validate existentes e a ciência do experimento.
Manter campaign fetch como antecipação explícita opcional.
Não misturar hoje renomeação, ecFlow, interface web ou migração completa para mpaswf com a execução de referência.

## Pendências para depois de terça-feira

1. Reconciliar código realmente publicado, configuração JACI, versões instaladas, workflow efetivo e resultados da campanha.
2. Inventariar responsabilidades duplicadas, especialmente PBS, WPS, MPAS e aquisição; documentar dono de cada operação.
3. Definir contratos de cada etapa: entradas/saídas, ciclo e janela, diretório, recursos, exit codes, manifestos e logs.
4. Separar comandos científicos de exportadores e atalhos de lançamento; definir descrição comum da campanha sem criar outro motor.
5. Consolidar reutilização do mpaswf para cold start e análise JEDI; verificar restart, streams e trajetória FGAT.
6. Uniformizar prepara/roda/valida mantendo registros internos para retomar aquisição/conversão sem repetir produtos válidos.
7. Padronizar diagnóstico: etapa/ciclo, esperado/encontrado, arquivo/configuração responsável, log e correção possível.
8. Testar retomada, transferência interrompida, falha PBS, dados ausentes, ciclos intermediários e compatibilidade de produtos.
9. Consolidar exportador simpleWorkflow; só depois implementar e testar ecFlow e comparar equivalência das dependências.
10. Avaliar renomeação, documentação e futura interface web após contratos estabilizados.

## Como retomar na quarta-feira

Ler este documento e o histórico recente da branch; não assumir que o código permaneceu no estado de 11/10.
Primeiro atualizar este registro com: commits/versões usados, etapas executadas, número de ciclos validados, IDs de jobs, erros pendentes, diretório da campanha e resultados apresentados.
Preservar execução em andamento e produtos de referência; alterações arquiteturais em branch/diretório separados.
Não reiniciar downloads, não regenerar campanha existente sem inspeção e não mudar configuração científica silenciosamente.
Escolher a primeira mudança após o inventário e validar sem depender do JACI: executar comandos científicos com processos simulados e gerar dependências equivalentes.
Depois validar um ciclo real antes de adotar mudanças nas campanhas de 7/30 dias.

## Critérios de conclusão

Mesmas etapas científicas utilizáveis manualmente e por diferentes orquestradores.
Nenhum download global oculto em geração; aquisição rastreável por etapa/ciclo.
Produtos validados antes de consumo; falhas não promovem análise/background inválidos.
Retomada preserva tentativas e reusa apenas produtos compatíveis.
Configuração simples, documentada, com parâmetros científicos efetivos e versões registrados.

## Atualização de urgência publicada em 11/10

Commits 5da363d até b1b9f274 na mesma branch:
- create/run/check não fazem aquisição global implícita;
- observations_doctor adquire somente o ciclo solicitado antes da verificação/conversão;
- wps_prepare adquire o GFS quando wps.acquisition está declarado e reutiliza arquivo local não vazio;
- preflight aceita observações ausentes com provider habilitado e URL declarada, sem baixar;
- materialização registra configuração de aquisição no profile.yaml do caso;
- scripts/configure_gfs_acquisition.py habilita aquisição no caso de origem e na inicialização materializada, mantendo comentários e parâmetros, com backup .before-acquisition;
- tutorial atualizado; 154 testes locais passaram.

Limite temporário: aquisição permanece dentro de comandos existentes (observations_doctor e wps_prepare), não na futura interface uniforme. Submissão/espera PBS ainda pertencem aos comandos atuais. Validação científica real no JACI continua pendente; não declarar 7 dias concluídos sem evidência.
Próximo passo do operador: pull da branch, executar o script com tutorial-2025-7d/campaign.yaml, executar campaign check e, se PASS, campaign run. Não recriar a campanha nem apagar dados/estado. Registrar o resultado efetivo aqui depois.

## Checkpoint JACI, 11/10 à noite

WPS prepare/run/validate/gate passaram. MPAS init job 669185.pbs-ha executou em cn-0001 com 128 CPUs, terminou em 1 segundo e Exit_status=1; stderr: mpiexec unexpected error - sgicheckppversion returned 0. Nenhum primeiro ciclo validado.
Comparação com M3 mostrou launcher explícito /opt/cray/pals/1.6/bin/mpiexec nos arquivos experiments/M3/native-cycle/{initial-mpas,cycling-mpas}/mpas.yaml, setup vazio. O workflow de 3dias executado começou em JEDI e usou background inicial já disponível; não comprova a nova inicialização GFS/WPS.
Templates corrigidos para PALS; script scripts/configure_jaci_pals.py corrige fontes e caso materializado mantendo backups e comentários, e recusa lançador customizado. 154 testes locais passaram; script verificado para preservação e reexecução.
Próximo passo: pull, executar configure_jaci_pals.py, reset do estado operacional simpleWorkflow (histórico preservado; seguro neste ponto porque o único job científico terminou com falha e nenhum ciclo começou), retomar campanha. Não presumir sucesso MPI antes do log real.

## Checkpoint previsão inicial, 11/10 21h

PALS permitiu MPAS init validar. Previsão inicial job 669358.pbs-ha falhou com signal 11 durante integração (~18:40Z), mensagem Stream diagnostics does not exist e extremos de velocidade anormais no primeiro passo. Referência M3/native-cycle/initial-mpas no commit 5aeed608 foi comparada: template novo omitia diagnostics/restart nos streams, seis coeficientes de difusão explícitos zero, printout/soundings e GFORTRAN_CONVERT_UNIT=big_endian:101-200. DT=1200 e mesoscale_reference são iguais e foram mantidos. Templates cíclicos coincidem com os da revisão científica 60cf1ea.
Correção publicada até b1522f10: namelist inicial restaurado literalmente, streams restaurados preservando nome de entrada mpas.init, endian adicionado e relatório de validação MPAS mostra caminhos resolvidos (o código já verificava caminhos resolvidos; não era erro de cálculo da data). Script restore_initial_mpas_reference.py atualiza fontes e configuração materializada com backups. 157 testes locais passaram. Não há prova de correção da queda científica até novo log real. Solicitar início de stderr para identificar exceção anterior ao backtrace, preservar produtos de WPS/init e não executar novo reset global.
