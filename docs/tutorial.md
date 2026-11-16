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

## 3. Primeiro experimento científico **real** — usando o simpleWorkflow

O pré-configurador `python -m monan_jedi_workflow.experiment_start` copia a
**receita científica instalada** `catalog/reference-20250901` (MPAS 240 km,
55 níveis, 128 ranks, matriz B correspondente, 3D-FGAT), cria `experiment.yaml`,
`initialization.yaml`, `init.yaml`, `science/`, os links dos backgrounds,
`campaign.yaml` e `run-worker.sh`. **Não executa o modelo, não instala o
ambiente, não baixa os dados e não submete PBS.**

A receita gerada corresponde a duas análises, em 01/09/2025 **00Z e 06Z**,
com a inicialização e a previsão intermediária necessárias. A consistência
estática de configurações históricas foi auditada, mas a equivalência numérica
científica na JACI ainda está **pendente**.

### 3.1 Ambiente Python e arquivos em /p

Na JACI, os compute nodes **não acessam o `$HOME`**. O `simpleWorkflow` é
executado no login e submete cada `run` científico como **job PBS independente**.
O `run-worker.sh`, chamado dentro de cada job, configura o `PATH` para um
ambiente Python compartilhado e verifica a instalação antes do processamento.

```bash
command -v python
command -v swf
command -v monan-jedi-workflow
python -c 'import sysconfig; print(sysconfig.get_path("scripts"))'
```

Confirme que o diretório `bin` indicado está visível nos compute nodes,
preferencialmente em `/p`. Se estiver em `/home` ou `/home2`, prepare um
ambiente acessível em `/p` antes de gerar o caso. Se necessário, indique
`--runtime-bin /p/caminho/do/ambiente/bin` ao gerar o experimento.
`#PBS -V` por si só não garante que os executáveis estarão acessíveis.

### 3.2 Defina NEW_CASE e gere um experimento **novo**

`NEW_CASE` é uma variável do shell que **você define**: contém o caminho absoluto
do diretório onde o pré-configurador criará os arquivos. O destino ainda não
pode existir e não é removido ou sobrescrito.

```bash
export NEW_CASE=/p/projetos/monan_das/joao.gerd/work/first-experiment-20250901-swf
echo "$NEW_CASE"
python -m monan_jedi_workflow.experiment_start "$NEW_CASE"
cd "$NEW_CASE"
ls experiment.yaml initialization.yaml init.yaml campaign.yaml run-worker.sh
```

Os caminhos científicos de GFS, PREPBUFR, GNSS-RO, malha, partição, tabelas de
física, matriz B e executáveis devem ser configurados por variáveis de
ambiente conforme **[receita operacional completa](first-experiment.md)**.
O pré-configurador não baixa esses dados. Não substitua arquivos históricos
por produtos artificiais.

### 3.3 Valide o plano e deixe o orquestrador submeter os jobs

```bash
campaign inspect campaign.yaml
campaign check campaign.yaml
campaign export campaign.yaml --engine simpleworkflow
swf validate workflow.yaml
swf plan workflow.yaml
```

A sequência declarada é WPS → MPAS Init → MPAS inicial → Obs2IODA 00Z →
JEDI 00Z → MPAS 00Z → Obs2IODA 06Z → JEDI 06Z. Para cada etapa,
`prepare`, `run` e `validate` são tarefas distintas e dependentes.
Somente as tarefas `run` que precisam de computação recebem alocação PBS.

Após conferir os insumos científicos, execute **no login**:

```bash
swf run workflow.yaml --ui plain
```

**Não use `qsub run-case.pbs`**. O novo pré-configurador não gera esse script
monolítico. O `simpleWorkflow` controla a submissão por etapa, os logs,
o status e a retomada conforme suas garantias de execução.

### 3.4 Resultados esperados

```bash
swf status workflow.yaml
jedi status experiment.yaml --cycle 2025-09-01T00:00:00Z
jedi status experiment.yaml --cycle 2025-09-01T06:00:00Z
```

Verifique o background consumido em cada análise, os NetCDF e IODA, os logs
PBS e a proveniência em `.simpleworkflow/runs/`. A validação científica exige
a comparação dos produtos com a referência histórica, documentada em
**[Validação científica de setembro de 2025](validation/2025-reference-scientific-validation.md)**.

**Status atual:** integração do pré-configurador ao exportador implementada;
a execução do novo DAG na JACI ainda não foi confirmada. Não confunda
`campaign check` ou `swf validate` com aprovação científica.

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
