# Tutorial oficial candidato — MONAN-JEDI por aplicativos (branch feat/platform-domain-apps)

> **Status:** roteiro operacional da beta 0.3.0b1. O teste de instalação usa dados artificiais. Uma campanha científica real na JACI só estará homologada após executar e validar os produtos do baseline, incluindo o acoplamento entre ciclos. Não confundir a interface atual com a interface legada `monan-jedi-workflow campaign create/run`.

## 0. Como a plataforma funciona

O usuário configura **um experimento científico** (`experiment.yaml`, arquivos JEDI/MPAS/observações e site) e **uma campanha** (`campaign.yaml`, datas, operações e output). Cada aplicativo processa um domínio para um único horário:

- `obs acquire`: aquisição dos dados;
- `obs convert`: conversão para IODA;
- `jedi`: análise;
- `mpas init`: inicialização, quando configurada, feita **uma vez**, fora do ciclo;
- `mpas`: previsão para alimentar o próximo horário;
- `diagnostics`: diagnósticos da execução;
- `campaign`: inspeciona, verifica e **exporta** a sequência para o **simpleWorkflow**, que executa e retoma tarefas.

Não é necessário escrever manualmente o grafo nem scripts de repetição. A versão beta ainda exporta uma tarefa por estágio e timestamp; não foi homologada para gerar/gerenciar um ano de tarefas na JACI.

## 1. Instalação em ambiente novo

```bash
git clone --branch feat/platform-domain-apps https://github.com/joaogerd/monan-jedi-workflow.git
cd monan-jedi-workflow
python -m pip install -e '.[dev,orchestration]'
obs --help
jedi --help
mpas --help
diagnostics --help
campaign --help
swf --help
```

Python >=3.10. Essa instalação **não** compila MONAN/MPAS, MPAS-JEDI, WPS ou Obs2IODA. Para execução científica, confirme previamente as instalações, bibliotecas, ambiente de site e dados. No JACI, os caminhos, o ambiente MPI/PBS e os recursos do caso não podem ser inferidos do exemplo artificial.

## 2. Teste rápido: um único ciclo **artificial**

Use este teste exclusivamente para confirmar a instalação e os contratos dos cinco aplicativos. Ele não prova que MONAN, JEDI ou Obs2IODA reais funcionaram.

```bash
mkdir -p /p/projetos/SEU_GRUPO/SEU_USUARIO/testes
cp -r examples/beta /p/projetos/SEU_GRUPO/SEU_USUARIO/testes/beta-ciclo
cd /p/projetos/SEU_GRUPO/SEU_USUARIO/testes/beta-ciclo
bash manual.sh experiment.yaml 2025-09-01T00:00:00Z
```

O script mostra uma linha `[OK]` para cada uma das cinco verificações (aquisição, conversão IODA, JEDI, MPAS e diagnósticos). Em cada etapa, exige que `prepare`, `run` e `validate` terminem sem erro e que `status --json` confirme `state: validated`. Somente quando **todas** passam imprime `TODOS OS 5 TESTES PASSARAM`. Se alguma falhar, encerra imediatamente com código diferente de zero, indica a operação e mostra as últimas linhas do log.

Exemplo de saída **esperada, não resultado de execução na JACI**:

```text
MONAN-JEDI | teste de instalacao (dados artificiais)
Ciclo: 2025-09-01T00:00:00Z

[OK] OBS — aquisicao — prepare / run / validate / status
[OK] OBS — conversao IODA — prepare / run / validate / status
[OK] JEDI — assimilacao — prepare / run / validate / status
[OK] MPAS — previsao — prepare / run / validate / status
[OK] DIAGNOSTICS — diagnosticos — prepare / run / validate / status

===========================================
 TODOS OS 5 TESTES PASSARAM
 Instalacao e contratos basicos: OK
 ATENCAO: produtos artificiais; NAO
          valida execucao cientifica real.
 Log completo: .../manual-test.log
===========================================
```

Substitua o caminho pelo destino autorizado do usuário. O log completo fica em `manual-test.log` no diretório do teste. Use uma cópia nova de `examples/beta` para evitar misturar resultados antigos. Os produtos deste fixture são **artificiais**, mesmo quando o comando termina com sucesso. Não reaproveite esse diretório para teste científico.

## 3. Primeiro experimento **real** — um ciclo

Crie uma pasta própria, nova, para cada tentativa. Parta da **receita científica de referência validada**: `experiment.yaml`, `site.yaml` (se usado), `science/jedi.yaml`, `science/mpas.yaml`, observações, templates, backgrounds, executáveis e arquivos de malha/partição. `examples/case` contém referências e marcadores `EDITAR` e **não** é um experimento pronto para rodar.

### 3.1 Inspecione os arquivos antes de executar

No arquivo principal, `experiment.destination` determina os produtos e o estado persistido. Caminhos de arquivos referenciados são relativos ao YAML que os declara. Verifique especialmente:

1. Aquisição ou arquivos observacionais existentes em cada horário, conversores e outputs IODA esperados;
2. Aplicação JEDI, background/estado completo, trajetória FGAT, B, geometria, variáveis, observadores, QC, executável e validação;
3. Previsão MPAS: malha, níveis, partição, passo de tempo, estados de saída e MPI;
4. Configuração de site: `site.execution.mode`, PBS real na JACI, bibliotecas, bootstrap, filas e recursos;
5. Diretórios independentes por ciclo e produtos previstos para alimentar o horário seguinte;
6. Para o primeiro ciclo, **estado inicial real** disponível ou sequência de inicialização declarada (não presumir que a beta prepara análises externas automaticamente).

Não mude a ciência durante a validação da plataforma. Guarde hashes/versões do baseline e logs.

### 3.2 Exercite os apps separadamente

Com um `experiment.yaml` científico completo, uma data com observações disponíveis e um destino novo:

```bash
CYCLE=2025-09-01T00:00:00Z   # EXEMPLO: substituir pelo ciclo do baseline
obs acquire inspect experiment.yaml --cycle "$CYCLE"
obs acquire check experiment.yaml --cycle "$CYCLE"
obs convert check experiment.yaml --cycle "$CYCLE"
jedi check experiment.yaml --cycle "$CYCLE"
mpas check experiment.yaml --cycle "$CYCLE"
diagnostics check experiment.yaml --cycle "$CYCLE"
```

Se alguma operação não fizer parte da receita, não a execute artificialmente; ajuste as operações selecionadas. Para cada app efetivamente usado, o ciclo de vida é `prepare -> run -> validate -> status`. Em site PBS, o `run` do worker científico depende da alocação gerenciada pelo simpleWorkflow (ou de alocação previamente obtida no uso manual). **Não** execute o mesmo ciclo em paralelo manualmente e pelo simpleWorkflow.

## 4. Campanha de **um dia** no simpleWorkflow

Depois de fechar o experimento científico, crie um `campaign.yaml` ao lado do principal:

```yaml
schema_version: 1
name: monan-jedi-1dia
experiment: ./experiment.yaml
calendar:
  start: '2025-09-01T00:00:00Z'
  end: '2025-09-02T00:00:00Z'
  interval: PT6H
  end_inclusive: false
operations: [obs.acquire, obs.convert, jedi, mpas, diagnostics]
last_cycle:
  forecast: true
output: ./workflow-1dia.yaml
```

Datas são ilustrativas: escolha uma janela real coberta pelos dados. `cycle.interval`, se declarado em `experiment.yaml`, deve coincidir com `calendar.interval`. O exemplo gera **4 análises**: 00, 06, 12 e 18 UTC. `end_inclusive: false` é essencial: sem isso, a beta inclui também 00 UTC do segundo dia. `last_cycle.forecast: true` mantém a previsão do último ciclo, necessária quando seu produto faz parte da verificação final.

Se for necessário inicializar o MPAS, configure a lista `initialization` separadamente, com referência a um experimento de inicialização válido. Exemplo estrutural (não é receita científica pronta):

```yaml
initialization:
  - operation: mpas.init
    cycle: '2025-08-31T18:00:00Z'
    experiment: ./initialization-experiment.yaml
  - operation: mpas
    cycle: '2025-08-31T18:00:00Z'
    experiment: ./initialization-experiment.yaml
```

A inicialização não faz parte da lista `operations` dos ciclos repetidos. A receita deve produzir explicitamente o estado exigido pelo primeiro JEDI.

### 4.1 Verifique, exporte, valide o plano e execute

```bash
campaign inspect campaign.yaml
campaign check campaign.yaml
campaign export campaign.yaml --engine simpleworkflow
swf validate workflow-1dia.yaml
swf plan workflow-1dia.yaml
swf run workflow-1dia.yaml --ui plain
```

O comando `campaign export` **não executa** a campanha; somente escreve o grafo. `swf run` é o executor. O arquivo de output deve **não existir** antes da exportação; para um novo teste escolha outro output e outro `experiment.destination`, preservando o resultado anterior.

A campanha de quatro horários e cinco operações gera até **60 tarefas de ciclo** (5 operações × prepare/run/validate × 4 horários), além das tarefas opcionais de inicialização. Isso é contagem do plano, **não** evidência de sucesso científico.

## 5. Aprovação científica: o que conferir

Para cada horário, preserve como evidências:

- produtos de aquisição e conversão IODA completos e válidos;
- execução e validação JEDI, análises e seus tempos NetCDF;
- forecast MPAS validado, inclusive o estado que alimenta o próximo ciclo;
- diagnósticos: função custo e departures quando disponíveis e configurados;
- logs PBS/simpleWorkflow, número de tarefas concluídas, erros e tempo de parede;
- continuidade de background, análise e forecast, sem reutilização de arquivos de outro experimento;
- comportamento de retomada após falha controlada, sem sobrescrever resultados válidos.

`check`, `swf validate` e o fixture artificial **não** substituem essa aprovação. Uma falha de validação interrompe a progressão do experimento. Um job PBS concluído não prova que o NetCDF ou a análise estejam corretos.

## 6. Ampliação: 3, 7, 30 e 365 dias

Use **o mesmo conjunto de arquivos científicos** e crie **uma campanha e um destino independentes para cada período**. Mantenha a data inicial, os parâmetros científicos e o intervalo, alterando somente o `calendar.end`, o nome e o `output`. Para início em 2025-09-01T00:00:00Z, intervalo PT6H, `end_inclusive: false`:

| Duração | end exclusivo (UTC) | Ciclos de 6h | Tarefas cíclicas máximas* |
| --- | --- | ---: | ---: |
| 1 dia | 2025-09-02T00:00:00Z | 4 | 60 |
| 3 dias | 2025-09-04T00:00:00Z | 12 | 180 |
| 7 dias | 2025-09-08T00:00:00Z | 28 | 420 |
| 30 dias | 2025-10-01T00:00:00Z | 120 | 1.800 |
| 365 dias | 2026-09-01T00:00:00Z | 1.460 | 21.900 |

*Cinco operações × três tarefas por operação, com previsão no último ciclo; não contam inicialização. Datas e números ilustram exclusivamente a cadência.

**Portão de promoção:** só iniciar 7 dias após aprovar 3 dias; 30 após aprovar 7; ano após aprovar 30. Verificar exportação, capacidade do scheduler, logs, retomada, uso de armazenamento e operações de longa duração antes da campanha anual. A beta exporta um grafo estático proporcional ao período: o ano exige ensaio de escalabilidade e, possivelmente, geração por janelas ou expansão dinâmica, sem mudança de ciência.

## 7. Limpeza e release

Antes de marcar a versão estável:

- [ ] Eleger **somente um** tutorial e uma interface pública; isolar a documentação legada;
- [ ] Distribuir uma receita científica real, versionada e sem paths pessoais, usando placeholders explícitos somente onde indispensáveis;
- [ ] Testar a instalação **fora** do checkout e o carregamento de `catalog:`;
- [ ] Fixar versões de `monan-jedi-workflow`, simpleWorkflow, MONAN/MPAS, MPAS-JEDI, Obs2IODA e stack;
- [ ] Validar mensagens de erro, contratos, restart, PBS e diagnósticos na JACI;
- [ ] Conferir que exemplo/fixture artificial e resultados reais estejam claramente separados;
- [ ] Consolidar documentação e executar testes automatizados e um ciclo científico real;
- [ ] Só então promover a branch para a primeira release estável, com tag, changelog e procedimento de migração.

Referência dos comandos da beta: [docs/beta-testing.md](beta-testing.md).
