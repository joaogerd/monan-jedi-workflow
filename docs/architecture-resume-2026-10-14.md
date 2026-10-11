# Retomada da arquitetura científica — 14/10/2026

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
