# Reinício controlado do experimento de setembro de 2025

Decisão de 12/10/2026: reconstruir a execução a partir dos cases M3 validados,
preservando a campanha anterior e os dados já adquiridos. A arquitetura maior
continua adiada conforme `architecture-resume-2026-10-14.md`.

## Referência e problema confirmado

Fontes institucionais: `GAD-DIMNT-CPTEC/monan-jedi-2026`,
`experiments/M3/3dias/`, `docs/relatorios/` e
`experiments/M3/native-cycle/evidence-7days-20260918/`.
Há registros de 13 análises na campanha histórica de três dias e 29 análises
na campanha nativa de sete dias, ambas com dados de abril de 2018.
Esses resultados não validam a campanha de setembro de 2025.

A primeira previsão de seis horas de 2025 foi validada depois de reutilizar
a geometria vertical do invariant. As observações do primeiro ciclo foram
convertidas e validadas. O JEDI abortou no job 674140.pbs-ha por ausência de
`streams.atmosphere.outer`; malha, partição e arquivos auxiliares também não
haviam sido preparados. A preparação incompleta explica essa tentativa; a
matriz B não chegou a ser testada pela assimilação.

Os cases de origem registrados nas evidências são:

```text
<workspace>/work/CASE/cases/jedi-2018041500-fgat-corrected
<workspace>/work/CASE/cases/mpas-2018041512-fgat-corrected
<workspace>/work/CASE/cases/mpas-2018041418-initial
```

O YAML arquivado de 2018 aponta a geometria para `geometry/2018041500/`.
Não se deve inferir sua localização somente pelo nome do diretório de execução.
O GitHub não contém todos os arquivos do runtime, e a proveniência registra
um perfil modificado localmente; consultar apenas o commit é insuficiente.

## Primeira ação: captura sem execução

`scripts/capture_m3_reference.py` produz um inventário e um tar.gz dos arquivos
pequenos dos cases e runtimes conhecidos. Registra caminhos originais, destinos
de links, SHA-256, diretórios ausentes e erros de leitura. Não captura NetCDF,
BUFR, matriz B, executáveis ou logs. Não submete jobs nem modifica a referência.
O pacote não é um novo case executável e não significa validação científica.

## Case novo e teste inicial

Preparar um novo diretório `experiments/2025-reference`, somente depois de
conferir a captura. Preservar os comentários dos YAMLs. Manter datas, caminhos
e dados em entradas explícitas; transportar integralmente os arquivos de suporte.
Usar a instalação atual apenas depois de conferir sua compatibilidade com a
referência. Não trocar binários nem copiar observações de 2018 silenciosamente.

O primeiro teste terá:

| Etapa | Horário científico |
|---|---|
| GFS/WPS e inicialização MPAS | 2025-08-31 18Z |
| Primeira previsão | 18Z → 00Z, com produtos em 21Z e 00Z |
| Primeira análise JEDI | 2025-09-01 00Z |
| Previsão entre análises | 00Z → 06Z, com produtos em 03Z e 06Z |
| Segunda análise JEDI | 2025-09-01 06Z |

Verificar todo o runtime antes de submeter: namelists, streams XML e listas de
campos, invariant, partição para o número real de ranks, geovars, keptvars,
alias de observações, tabelas físicas, matriz B e background completo.

Preservar o contrato científico: 3D-FGAT, janela de seis horas, background T−3h,
estado completo em T, PT20M = 1200 s, física equivalente no JEDI e MPAS,
DRPCG e filtros da referência. PREPNR 2025 é uma escolha de fonte documentada;
não afirmar equivalência do conjunto observacional com PREP48H 2018.

Aceite: término dos jobs com sucesso, validações científicas, OOPS Ending,
incrementos não triviais, campos auditados finitos, outputs nos horários corretos
e consumo do background efetivamente produzido pelo ciclo anterior.
Testes locais do código não substituem esse aceite na JACI.

## Ampliação do período

| Experimento | Período inclusive | Análises a cada seis horas |
|---|---|---:|
| Teste de continuidade | 2025-09-01 00Z → 2025-09-01 06Z | 2 |
| Sete dias | 2025-09-01 00Z → 2025-09-08 00Z | 29 |
| Trinta dias | 2025-09-01 00Z → 2025-10-01 00Z | 121 |
| 365 dias | 2025-09-01 00Z → 2026-09-01 00Z | 1461 |

Cada ampliação exige continuidade do estado e retomada conferida. O registro
nativo de 2018 documenta reexecução da initialization ao mudar `--from`; portanto
não assumir que alterar a duração preservará todos os estados automaticamente.
Conferir essa semântica antes da extensão e impedir dois controladores ativos.

Para um ano ou até uma data recente, definir um término UTC explícito, conferir
a disponibilidade e cobertura observacional e planejar atualização das forçantes
de superfície. A configuração M3 usa `config_sst_update = false`; repetir essa
configuração por um ano precisa de uma decisão científica explícita.
A B usada precisa ter sua origem e limitações registradas. Nenhum novo cálculo
de B faz parte do reinício imediato.

## Estado na publicação deste documento

- Captura real recebida: 5541 arquivos, sem erros de captura; todos os hashes conferidos.
- Doze arquivos do runtime JEDI executado preservados em `examples/m3-reference-assets/`.
- MPI real da referência: 128 processos, endian GNU explícito e namelists outer/inner distintos.
- Gerador do case novo: `scripts/create_2025_reference.py`; recusa sobrescrita,
  preserva as fontes observacionais do tutorial e confere entradas fixas.
- Preparação completa da geometria conferida em teste local com fixtures NetCDF.
- Case novo criado na JACI. Inicialização WPS/init/MPAS, primeiro background e
  observações 00Z passaram pelas validações. A primeira análise JEDI 00Z também
  passou no comando `jedi-validate` na JACI.
- Retomada bloqueou antes de `jedi_validate`: o adaptador tinha emitido
  `{analysis_mpas_file_time}` como artefato do simpleWorkflow, que só conhece
  campos temporais genéricos. Corrigido na geração dos caminhos; campanhas já
  materializadas recebem a mesma correção ao retomar, com backup do workflow,
  sem reset do estado nem alteração das configurações científicas.
- Operador informou conclusão dos sete dias em 12/10/2026: último ciclo
  2025-09-08T00:00:00Z passou por `jedi_validate` e `jedi_gate`.
  Métricas e figuras de 2025 ainda devem ser extraídas dos resultados na JACI;
  não usar os valores de 2018 como resultados da nova campanha.

## Comandos para o próximo passo na JACI

```bash
cd /p/projetos/monan_das/$USER/projects/monan-jedi-workflow
git pull --ff-only origin feature/2025-reference-case
python scripts/create_2025_reference.py \
  --source tutorial-2025-7d \
  --destination experiments/2025-reference
monan-jedi-workflow campaign check experiments/2025-reference/campaign.yaml
```

Após o preflight passar, executar o teste com `campaign run`. Antes de iniciar
a campanha `campaign-7d.yaml`, conferir as duas análises e a previsão entre elas.
Uma tentativa anterior ativa precisa terminar antes de iniciar outro controlador.

## Retomada após o erro de artefato da análise

O case `experiments/2025-reference` já existe. Não executar novamente o gerador
nem `swf reset`. O código atualizado corrige os caminhos de saída de
`jedi_validate` e entrada de `mpas_prepare` no workflow existente. Backup:
`workflow.yaml.before-analysis-artifact-fix`. O caminho científico continua
`Data/states/mpas.3dfgat.YYYY-MM-DD_HH.00.00.nc` nos ciclos horários da campanha.
O adaptador de campanha exige início em hora UTC inteira e intervalo em horas
inteiras; rejeita minutos/segundos não nulos em vez de produzir nomes errados.
Comandos de etapas individuais mantêm suporte aos timestamps completos.

A primeira tradução tentou usar índices `{cycle_id[11]}` para minutos e
segundos; o validador de caminhos do simpleWorkflow rejeitou os colchetes como
glob. A tradução agora usa apenas campos genéricos de data e hora, sem índices.
A retomada também reconhece e corrige o workflow dessa tentativa intermediária.
Não é necessário atualizar o simpleWorkflow.

```bash
cd /p/projetos/monan_das/$USER/projects/monan-jedi-workflow
git pull --ff-only origin feature/2025-reference-case
CASE=experiments/2025-reference/cases/monan-jedi-20250901-smoke
monan-jedi-workflow jedi-validate "$CASE" --cycle 2025-09-01T00:00:00Z
```

Se a validação científica passar, retomar a mesma campanha:

```bash
set -o pipefail
monan-jedi-workflow campaign run experiments/2025-reference/campaign.yaml \
  2>&1 | tee -a experiments/2025-reference/teste-continuidade.log
```

Verificação local da correção: 178 testes passaram. O erro dos colchetes foi
reproduzido no `load_workflow` real do simpleWorkflow; workflows novos e migrados
passaram nesse validador. Comandos e 986 caminhos obrigatórios dos 29 ciclos
foram resolvidos usando o `CycleContext` e `resolve_task_artifacts` reais do
simpleWorkflow. Isso verifica o adaptador; não substitui as validações
científicas na JACI.

## Figuras da campanha de sete dias concluída

As mesmas três categorias do relatório M3 de três dias são produzidas por:

```bash
cd /p/projetos/monan_das/$USER/projects/monan-jedi-workflow
git pull --ff-only origin feature/2025-reference-case
python scripts/generate_campaign_figures.py \
  experiments/2025-reference/cases/monan-jedi-20250901-7d
```

O script exige NumPy, netCDF4, PyYAML e Matplotlib, já listados no ambiente do
tutorial. Ele não submete jobs nem modifica os estados/arquivos científicos.
Lê SQLite em modo somente leitura, confere os ciclos contra a campanha,
valida os manifests JEDI/MPAS/Obs2IODA e exige `OOPS Ending` por ciclo.
Emite progresso por ciclo e erro com o arquivo/grupo ausente.

Saída: `cases/monan-jedi-20250901-7d/diagnostics/`:

- `figures/campaign_completion.{png,pdf,svg}`: contagem acumulada de análises
  e previsões entre ciclos validadas.
- `figures/jedi_cost_convergence.{png,pdf,svg}`: J/J₀ para cada ciclo;
  J₀ vem do custo não linear antes do minimizador, os demais valores são
  os custos quadráticos J das iterações internas. Componentes Jb/JoJc são
  excluídos. Mais de um outer loop é rejeitado explicitamente.
- `figures/omb_oma_rmse_airTemperature.{png,pdf,svg}`: RMSE de O−B/O−A
  da temperatura de radiossondas em cada ciclo, incluindo todos os níveis.
- `campaign_summary.csv`, `jedi_convergence.csv`, `jedi_cost_iterations.csv`,
  `omb_oma_sondes_airTemperature.csv`, `diagnostic_summary.json` e `report.md`.

As estatísticas observacionais usam a mesma amostra para O−B e O−A: valores
finitos, missing values excluídos, QC=0 na interseção dos grupos EffectiveQC0/1
disponíveis, ou EffectiveQC quando não houver grupos numerados. Grupos usados
são registrados por ciclo. Ausência de QC interrompe o cálculo, sem incluir
rejeitados silenciosamente. A seleção QC do script histórico de três dias
não está preservada nos CSVs: temos as mesmas métricas e tipos de figura,
mas a equivalência exata de seleção entre anos precisa ser conferida.

RMSE médio do período é a média aritmética dos RMSEs de cada ciclo, como
no relatório M3; não é o RMSE de todas as observações concatenadas. Melhorar
O−A em todos os ciclos não é condição artificial de sucesso: eventuais
aumentos são registrados. São observações assimiladas, não verificação
independente de previsões. O número de conversões vem do estado real do
workflow, não é inferido do número de previsões.

O script recusa sobrescrever um diretório de evidências existente. Para outra
geração, escolha `--output CAMINHO_NOVO`. Para transferir os resultados:

```bash
tar -czf experiments/2025-reference/diagnostics-7d-2025.tar.gz \
  -C experiments/2025-reference/cases/monan-jedi-20250901-7d diagnostics
```
