# Referência de configuração da campanha (interface atual)

> **Branch:** `develop`. Este arquivo descreve a estrutura consumida por `monan_jedi_workflow/platform_campaign.py` e **não** o antigo `campaign.duration`. Primeiro aprenda o fluxo completo no [tutorial](../tutorial.md).

## O que é uma campanha?

Uma campanha identifica **qual configuração científica executar** (`experiment`), **em quais horários** (`calendar`), **quais operações** e **onde exportar** seu grafo (`output`). O arquivo da campanha é distinto de `experiment.yaml`: alterações na campanha não devem mudar silenciosamente a física de um experimento.

O arquivo é criado automaticamente por `experiment create`. Para um usuário novo, **prefira o arquivo gerado**; o exemplo a seguir explica seu formato, não é um experimento executável completo:

```yaml
schema_version: 1
name: exemplo-1dia
experiment: ./experiment.yaml
calendar:
  start: '2026-01-30T00:00:00Z'
  end: '2026-01-31T00:00:00Z'
  interval: PT6H
  end_inclusive: false
operations:
  - obs.convert
  - jedi
  - mpas
last_cycle:
  forecast: false
output: ./workflow.yaml
```

Neste exemplo, o primeiro ciclo é às 00Z de 30/01 e o último às 18Z: **quatro análises JEDI**. `last_cycle.forecast: false` omite a previsão posterior à última análise, portanto são três previsões. A execução real requer que os arquivos científicos, as observações e os backgrounds correspondentes existam; **editar a duração não os produz**.

## Chaves verificadas na implementação

| Chave | Função |
| --- | --- |
| `schema_version` | Versão do formato; no branch atual deve ser `1` |
| `name` | Nome da campanha, usado no workflow exportado |
| `experiment` | Referência ao `experiment.yaml`, relativa ao diretório da campanha |
| `calendar.start` | Primeira análise, em UTC |
| `calendar.end` | Limite final do calendário, em UTC |
| `calendar.interval` | Passo temporal ISO-8601 em horas inteiras positivas, por exemplo `PT6H` |
| `calendar.end_inclusive` | Inclui (`true`, padrão atual) ou exclui (`false`) o horário final |
| `operations` | Sequência de operações repetidas em cada ciclo |
| `last_cycle.forecast` | Incluir previsão MPAS após o último ciclo (padrão atual: `true`) |
| `initialization` | Lista opcional de etapas iniciais anteriores à primeira análise |
| `output` | Destino do `workflow.yaml` exportado |

Operações repetidas atualmente reconhecidas: `obs.acquire`, `obs.convert`, `jedi`, `mpas` e `diagnostics`. As operações `wps` e `mpas.init` pertencem à seção `initialization`, **não** à lista repetitiva. A ordenação declarada precisa respeitar as dependências entre aquisição, conversão, análise, previsão e diagnósticos.

Uma inicialização é declarada como lista de entradas com `operation`, `cycle` e, quando necessário, `experiment`. **Não invente uma inicialização editando o YAML sem garantir o estado científico exigido pelo primeiro JEDI.** Consulte o `campaign.yaml` criado por `experiment create`.

## Verificar e exportar

```bash
cd "$CASE"
source ./environment.sh
experiment check campaign.yaml
experiment export campaign.yaml
experiment validate workflow.yaml
experiment plan workflow.yaml
```

`experiment check` não executa a ciência. `experiment export` cria `workflow.yaml` e **recusa sobrescrever um workflow existente**. Para outra campanha use novo diretório/arquivo; não apague o estado de uma execução antiga para reaproveitar o nome.

### Atenção a campanhas de 3 e 7 dias

Com final **inclusivo** e passo de seis horas, 72 h representam **13 análises** e 168 h representam **29 análises**. Com final **exclusivo**, os mesmos limites representam 12 e 28 análises. Para a receita científica atual, `experiment create --duration P3D` ou `--duration P7D` gera os vínculos de background intermediários conforme a receita. `experiment check-inputs .` verifica o GFS de inicialização e os arquivos observacionais de **todos os ciclos** declarados, sem substituir a verificação do ambiente científico e PBS.

## Interface antiga

Documentos anteriores utilizavam `campaign: {start, duration, cycle_interval_hours, destination}`, `profile` e `execution.swf_command`. Esse é **outro formato**, ligado à interface legada. Não o misture com o arquivo descrito aqui nem o ensine como entrada de `experiment check`/ `experiment export` nesta branch.
