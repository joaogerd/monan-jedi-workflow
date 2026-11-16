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

## 3. Primeiro experimento **real** — receita científica instalada (duas análises)

**Qual é a receita?** Ela vem instalada no pacote, no catálogo `monan_jedi_workflow/catalog/reference-20250901/`. É a configuração de referência de **1º de setembro de 2025**, com malha x1.10242 (~240 km), 55 níveis, matriz B correspondente, 128 ranks MPI, 3D-FGAT e intervalo de 6 horas. O primeiro teste executa análises em **00Z e 06Z**, com uma previsão entre elas, para verificar a passagem de estados. A consistência estática dos templates foi auditada, mas **a execução e a equivalência numérica na JACI ainda não foram homologadas**.

**Não copie `examples/case` para o primeiro teste real**: ele contém `EDITAR` e não é uma receita pronta. **Não use `examples/beta`**: é exclusivamente artificial. Não é necessário encontrar um antigo `jedi.yaml`, nem criar manualmente os YAMLs.

A receita é criada pelo comando:

```bash
python -m monan_jedi_workflow.experiment_start --help
python -m monan_jedi_workflow.experiment_start "$NEW_CASE"
```

O comando recusa sobrescrever um destino existente, copia o catálogo e materializa `experiment.yaml`, `initialization.yaml`, `init.yaml`, `science/` e `run-case.pbs`. **Ele cria configurações; não baixa os dados científicos nem executa o modelo.**

### 3.1 Confirme o pacote instalado e as dependências

No checkout atualizado do branch `feat/platform-domain-apps`, com o ambiente MONAN-JEDI ativado:

```bash
cd /p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow
git switch feat/platform-domain-apps
git pull --ff-only
python -m pip install --no-deps --no-build-isolation -e .
python -m monan_jedi_workflow.experiment_start --help
```

A instalação do workflow não instala/compila MONAN/MPAS, MPAS-JEDI, WPS ou Obs2IODA. O Python e o ambiente de runtime precisam funcionar nos nós de computação, não apenas no login. Antes de submeter, confira o manifesto real da instalação e as bibliotecas MPI/PBS.

### 3.2 Declare os caminhos e confira os arquivos de entrada

Estes caminhos são os **valores documentados para o ambiente de João na JACI**; confirme que existem no filesystem. Não são valores universais nem arquivos automaticamente disponibilizados pelo pacote.

```bash
export STACK_ROOT=/p/projetos/monan_das/joao.gerd/work/spack-stack-inpe-overlay-20260515T181917Z/spack-stack
export MONAN_JEDI_INSTALL_ROOT=/p/projetos/monan_das/$USER/build/monan-jedi
export MONAN_MESH_ROOT=/p/projetos/monan_das/share/MONAN-JEDI-Data/meshes/quasi_uniform/x1.10242_240km
export MONAN_PHYSICS_ROOT=/p/projetos/monan_das/share/MONAN-JEDI-Data/physics/mpas/files
export MONAN_BMATRIX_ROOT=/p/projetos/monan_das/share/MONAN-JEDI-Data/covariance/x1.10242_240km/55levels
export MONAN_LIBFABRIC_ROOT=/opt/cray/libfabric/1.22.0/lib64
export MONAN_INPUT_ROOT=/p/projetos/monan_das/$USER/external-inputs
export MONAN_GFS_ROOT=/p/projetos/monan_das/$USER/data/gfs
export NEW_CASE=/p/projetos/monan_das/$USER/work/first-experiment-20250901
```

Verifique a **existência e legibilidade** dos insumos reais, antes de gastar recursos computacionais:

```bash
test -r "$MONAN_JEDI_INSTALL_ROOT/share/monan-jedi/install-manifest.json" && echo "Manifesto: OK"
test -r "$MONAN_MESH_ROOT/static/x1.10242.invariant.nc" && echo "Malha: OK"
test -r "$MONAN_MESH_ROOT/partitions/x1.10242.graph.info.part.128" && echo "Particao: OK"
test -d "$MONAN_BMATRIX_ROOT" && echo "Diretorio B: existe (conteudo ainda precisa ser validado)"
test -r "$MONAN_GFS_ROOT/2025083118/gfs.t18z.pgrb2.0p25.f000" && echo "GFS inicial: OK"
test -r "$MONAN_INPUT_ROOT/observations/prepnr/2025/prepbufr.gdas.2025090100.nr" && echo "PREPBUFR 00Z: OK"
test -r "$MONAN_INPUT_ROOT/observations/prepnr/2025/prepbufr.gdas.2025090106.nr" && echo "PREPBUFR 06Z: OK"
test -r "$MONAN_INPUT_ROOT/observations/gpsro/2025/gdas.gpsro.t00z.20250901.bufr" && echo "GNSS-RO 00Z: OK"
test -r "$MONAN_INPUT_ROOT/observations/gpsro/2025/gdas.gpsro.t06z.20250901.bufr" && echo "GNSS-RO 06Z: OK"
```

**Atenção:** os `test` individuais não produzem erro detalhado quando falham; a ausência de `OK` significa que aquele caminho deve ser investigado. A existência do diretório B não comprova a presença de todos os arquivos de covariância. A receita **não** faz download automático desses insumos históricos. Não substitua por dados artificiais ou de outra data.

### 3.3 Gere o primeiro experimento sem copiar arquivos à mão

```bash
python -m monan_jedi_workflow.experiment_start "$NEW_CASE"
cd "$NEW_CASE"
ls -l experiment.yaml initialization.yaml init.yaml run-case.pbs
```

A estrutura criada inclui `science/jedi.yaml`, `science/mpas.yaml`, `science/obs2ioda.yaml`, os arquivos de inicialização, os templates e os wrappers. Se `$NEW_CASE` já existir, escolha **outro diretório vazio e ainda inexistente**; não apague um resultado anterior para reutilizar o nome.

### 3.4 Inspecione o caso antes de submeter

```bash
obs convert check experiment.yaml --cycle 2025-09-01T00:00:00Z
obs convert check experiment.yaml --cycle 2025-09-01T06:00:00Z
jedi inspect experiment.yaml --cycle 2025-09-01T00:00:00Z
mpas inspect initialization.yaml --cycle 2025-08-31T18:00:00Z
cat run-case.pbs
```

Os dois `check` precisam terminar sem erro. `inspect` mostra a configuração e os caminhos, inclusive produtos que só existirão após as etapas produtoras; não confunda inspeção com aprovação científica. Confira especialmente o `#PBS -q`, `select`, `mpiprocs`, `walltime` e a visibilidade dos executáveis no compute node.

### 3.5 Submeta o primeiro teste científico

```bash
qsub run-case.pbs
```

A receita gera **um shell PBS sequencial**, não um `workflow.yaml` do simpleWorkflow. O shell executa WPS, `mpas init`, a previsão inicial, as observações e JEDI 00Z, MPAS 00Z e JEDI 06Z. WPS ainda usa a interface legada. **Não execute esse shell no login** e não rode simultaneamente o simpleWorkflow sobre o mesmo caso.

### 3.6 Verifique o resultado

Após o job concluir:

```bash
jedi status experiment.yaml --cycle 2025-09-01T00:00:00Z
jedi status experiment.yaml --cycle 2025-09-01T06:00:00Z
python -m monan_jedi_workflow.scientific_feedback \
  work/jedi/20250901T000000Z/Data/os/obsout_3dvar_sondes.nc4
python -m monan_jedi_workflow.scientific_feedback \
  work/jedi/20250901T060000Z/Data/os/obsout_3dvar_sondes.nc4
```

Esperado: as duas análises validadas, PREPBUFR/GNSS-RO convertidos conforme o caso, MPAS inicial e MPAS intermediário validados, backgrounds nos horários apropriados e feedback observacional verificável. Consulte `case.stdout.log`, `case.stderr.log` e os logs de cada runtime. O shell para na primeira falha; **não possui restart automático**.

Para os detalhes completos deste procedimento e do inventário dos dados, consulte **[Primeiro experimento real](first-experiment.md)**. Para a comparação numérica com a referência histórica (que exige os dados originais de comparação), consulte **[Validação científica](validation/2025-reference-scientific-validation.md)** e **[Piloto curto](validation/run-short-pilot.md)**.

**Importante para a futura versão 1.0:** o procedimento acima é um ensaio real de **dois ciclos encadeados usando um shell PBS**, ainda não a campanha de um dia gerenciada pelo simpleWorkflow. A etapa seguinte exige integrar e validar essa mesma receita no formato de campanha, com inicialização e transferência de background corretas; não basta criar um `campaign.yaml` genérico para afirmar que isso está pronto.

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
