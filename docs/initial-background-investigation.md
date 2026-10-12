# Investigação da previsão inicial de 2025 versus M3 de três dias

Data: 11/10/2026, noite. Campanha de 7 dias ainda não iniciou o primeiro JEDI.

## Evidências confirmadas

- M3 executada: experiments/M3/3dias/executed/workflow.yaml no commit 5aeed60857447bf229416327441589ca52e29e39 começa em jedi2018041500_prepare. Não contém a cadeia GFS/WPS/mpas_init/primeira previsão que está sendo testada em 2025.
- Primeiro JEDI histórico lê Data/background/2018041500/mpasout.2018-04-14_21.00.00.nc, conforme configs/jedi/20180415T000000Z/3dfgat.bmatrix.yaml.
- A configuração initial-mpas arquivada em native-cycle aponta a um estado inicial NCAR já existente, de 2018041418. Presença dessa configuração não prova execução do cold start dentro dos 185 passos dos três dias.
- Novos dados: GFS 2025083118 f000 -> WPS -> mpas_init_atmosphere -> previsão inicial -> JEDI. Há uma cadeia nova anterior ao sistema já validado.
- Job 669185 falhou no lançador MPI genérico. PALS explícito corrigiu o lançamento; WPS e mpas_init passaram nos critérios atuais.
- Jobs 669358 e 669403 iniciaram o modelo e caíram por SIGSEGV. O último usou PALS, endian declarado, pesqmidi e 128 ranks. Durou 19 s; Exit_status=143 veio após uma rank morrer por signal 11.
- Extremos do primeiro passo se repetem: w aproximadamente +/-13000 m/s; u máximo aproximadamente 1026617 m/s. Valores fisicamente incompatíveis com uma previsão atmosférica normal, mas o log pós-passo não prova que já estavam no arquivo inicial.
- Omissoes nos templates iniciais (diagnostics/restart, difusão explícita, controles printout/soundings, endian) foram restauradas. A ausência de diagnostics deixou de aparecer, mas SIGSEGV permaneceu.
- DT=1200 s também existe na referência. Não foi demonstrado que reduzir DT resolve a origem do problema.

## Validação insuficiente da inicialização

init_stage.validate_mpas_init verifica existência dos arquivos e marcadores declarados. O exemplo tem required_log_markers vazio. Portanto o OK não prova término limpo, campos finitos, plausibilidade física ou compatibilidade geométrica. A primeira condição inicial permanece cientificamente não validada.

## Hipótese principal a testar: geometria vertical incompatível

A inicialização usa config_vertical_grid=true e recomputa zgrid/métricas.
A previsão lê x1.10242.invariant.nc em stream invariant separado.
No Registry.xml atmosférico da revisão MPAS 0e5a47a0e1bcccd6e3d99909b76e740a643c4db6:
- invariant contém zgrid, dzu, rdzu, rdzw, zz, zxu, fzm/fzp e outras métricas;
- input inclui invariant somente sob o pacote no_invariant_stream;
- com invariant separado, os campos meteorológicos de input são associados à geometria do invariant, não automaticamente à geometria recalculada no novo init.

Ter 55 níveis em ambos não comprova igualdade das alturas/métricas. Essa discrepância pode ocorrer silenciosamente e precisa ser medida. Ainda não se afirma que ocorreu nos arquivos JACI.

## Outras hipóteses

- Campos ausentes, mascarados, não finitos ou já extremos na condição inicial.
- Mudança do executável/compilação entre a instalação histórica builds/monan-jedi-mpas e a atual build/monan-jedi. Caminhos diferentes não provam binários diferentes; comparar SHA e manifestos.
- Interpolação da entrada GFS/níveis/solo. O namelist de init atual coincide com o template mpaswf para x1.10242, inclusive nfglevels=35; não alterar esse número sem inventário do WPS.
- Instabilidade da integração com a condição inicial atual, mesmo com DT idêntico ao histórico.
- Erro em rotina de física/dinâmica identificado pelas primeiras funções reais do backtrace; mensagens SIGSEGV repetidas não localizam a rotina.

## Próxima evidência necessária

Executar scripts/diagnose_initial_background.py tutorial-2025-7d/campaign.yaml no JACI. O script é somente leitura e reporta:
- fontes realmente declaradas do init, invariant e executável;
- dimensões e estatísticas de campos;
- diferenças de grade e métricas;
- espessura vertical, valores mascarados/não finitos;
- SHA do executável e comparação histórica opcional;
- funções únicas do backtrace e final do log init.

Não submeter novos jobs nem alterar DT/grade antes da evidência. Se as métricas diferirem, escolher e implementar uma única geometria coerente para inicialização, previsão, JEDI e B; não simplesmente trocar o invariant por um init de 2025 em todos os ciclos.
Se geometria coincidir, usar campos/rotina de falha para reduzir hipóteses. Produtos de WPS/init e histórico devem ser preservados.

## Fontes

- https://github.com/GAD-DIMNT-CPTEC/monan-jedi-2026/blob/5aeed60857447bf229416327441589ca52e29e39/experiments/M3/3dias/executed/workflow.yaml
- https://github.com/GAD-DIMNT-CPTEC/monan-jedi-2026/blob/5aeed60857447bf229416327441589ca52e29e39/experiments/M3/native-cycle/initial-mpas/mpas.yaml
- https://github.com/MPAS-Dev/MPAS-Model/blob/0e5a47a0e1bcccd6e3d99909b76e740a643c4db6/src/core_atmosphere/Registry.xml
- https://github.com/joaogerd/mpaswf/blob/main/templates/x1.10242/namelist.init_atmosphere.in

## Evidência recebida em 11/10 21:33 e correção publicada

Diagnóstico JACI confirmou: mesma malha horizontal e 55 níveis, mas zgrid difere até 350.60670446227914 m, zz até 0.308653180776554, com outras métricas diferentes. Campos iniciais u entre -134.83 e 135.15 m/s, w entre -0.1655 e 0.2172 m/s, rho positiva e campos amostrados sem valores mascarados/não finitos. qv tem mínimo -2.90e-5, a investigar se persistir problema; estatísticas não equivalem a validação física completa.
Log init terminou com Finished running the init_atmosphere core e zero erros/críticos. A inconsistência geométrica passou pelo antigo verificador de existência. Os bins diferem: atual cec6e0342d946ac10b64104e2431efaf99b5939bf38ccd22bd924a0f01bd3dae; histórico a8d2bb968f248c3f1adc4a3c3cea70cf0e99559dafb951f7af91e8b2b5cf2aad.
Backtrace localizou summarize_timestep, mpas_atm_time_integration.F:8618. Na revisão upstream pinada, a região busca índices de extremos e acessa latCell(indexMax); não atribuir o SIGSEGV à origem física sem comprovar a nova integração.
Correção específica: config_vertical_grid=false, mantendo config_met_interp=true e lendo coordenadas/métricas existentes. Conferido em mpas_init_atm_core_interface.F: met_stage_in fica ativo com met_interp e sem recomputar vertical/static/GWD. Input do init lê as métricas pelo pacote met_stage_in.
Incluída validation.geometry_reference no init, comparando zgrid e métricas com tolerância explícita rtol=1e-7, atol=1e-8. Estado incompatível bloqueia a validação; marcador de término limpo também exigido no exemplo. Scripts/reuse_invariant_vertical_grid.py atualiza fontes e caso materializado, preserva estado anterior em before-invariant-grid e backups dos parâmetros. 162 testes locais passaram. Próximo passo: regenerar somente init_atmosphere; validar geometria; depois repetir previsão inicial. Não modificar invariant compartilhado, B, DT ou executável no mesmo teste. Sucesso científico ainda pendente de nova execução JACI.
