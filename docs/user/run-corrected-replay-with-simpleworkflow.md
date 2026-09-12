# Executar a campanha corrected com simpleWorkflow

Este procedimento reproduz a campanha de referência validada de **analysis 00Z até analysis 18Z** usando `simpleWorkflow` como orquestrador externo dos stages `monan-jedi-workflow`.

O objetivo desta rodada não é redescobrir a configuração científica. O contrato JEDI/MPAS/Obs2IODA já foi validado. O objetivo é comprovar que a mesma sequência pode ser executada em namespace limpo, com dependências cross-cycle e gates `valid=true` explícitos.

## Escopo

A DAG contém:

```text
JEDI00
  |
  +--> MPAS00->06 ----+
  |                    |
  +--> Obs2IODA06 -----+--> JEDI06
                            |
                            +--> MPAS06->12 ----+
                            |                    |
                            +--> Obs2IODA12 -----+--> JEDI12
                                                     |
                                                     +--> MPAS12->18 ----+
                                                     |                    |
                                                     +--> Obs2IODA18 -----+--> JEDI18
```

Não existem tarefas `Obs2IODA00` nem `MPAS18->00` neste replay.

## Pré-requisitos

Entre na JACI pelo ambiente normal:

```bash
source /p/projetos/monan_das/joao.gerd/work/CASE/case-enter.sh
```

Use a branch de orchestration:

```bash
cd /p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow
git fetch origin
git switch agent/multicycle-corrected-orchestration
git pull --ff-only
```

Instale/atualize as CLIs no ambiente ativo conforme o procedimento normal do projeto e confirme:

```bash
monan-jedi-workflow --help
swf --help
```

## 1. Materializar um case limpo

O template JEDI deve ser o **corrected JEDI00**, porque o 00Z possui a variante documentada de 62 variáveis e esse contrato aceita naturalmente o estado de 63 variáveis dos ciclos posteriores. A ciência não é alterada; apenas os caminhos de handoff são redirecionados para o novo namespace.

```bash
DEST=/p/projetos/monan_das/joao.gerd/work/CASE/cases/reference-replay-20180415

 test ! -e "$DEST"

monan-jedi-workflow materialize-corrected-replay \
  --initial-jedi-case /p/projetos/monan_das/joao.gerd/work/CASE/cases/jedi-2018041500-fgat-corrected \
  --cycling-jedi-case /p/projetos/monan_das/joao.gerd/work/CASE/cases/jedi-2018041500-fgat-corrected \
  --mpas-case /p/projetos/monan_das/joao.gerd/work/CASE/cases/mpas-2018041512-fgat-corrected \
  --obs2ioda-config /p/projetos/monan_das/joao.gerd/work/CASE/obs2ioda.yaml \
  --workflow-template examples/simpleworkflow/cycled_da/corrected-replay-20180415.workflow.yaml.example \
  --destination "$DEST"
```

O materializador:

- recusa destino já existente;
- recusa source case contendo runtime/control state ou produtos científicos dependentes de ciclo;
- copia somente configuração/static assets do case JEDI template;
- preserva B, executáveis e assets exógenos declarados;
- materializa como inputs iniciais apenas o estado de trajetória 21Z, o analysis-base state 00Z e os três inputs observacionais já estabelecidos para 00Z;
- redireciona JEDI06/12/18 para produtos MPAS/IODA produzidos dentro de `DEST/work`;
- redireciona todos os MPAS para a análise JEDI do mesmo ciclo produzida dentro de `DEST/work`;
- não copia analyses/forecasts/IODA 06/12/18 da campanha de referência.

## 2. Auditar o case antes do simpleWorkflow

O namespace deve conter apenas configuração e starting inputs. Em particular, ainda não devem existir produtos JEDI/MPAS de 00/06/12/18.

Inspecione:

```bash
find "$DEST" -maxdepth 4 -type f -o -type l | sort
```

Confirme os starting inputs:

```text
work/mpas/20180414T180000Z/mpasout.2018-04-14_21.00.00.nc
work/mpas/20180414T180000Z/mpasout.2018-04-15_00.00.00.nc
work/obs/2018041500/sondes_obs_2018041500.h5
work/obs/2018041500/sfc_obs_2018041500.h5
work/obs/2018041500/gnssro_obs_2018041500.h5
```

Eles são starting inputs; não são produtos regenerados pelo replay.

## 3. Planejar a DAG

```bash
swf plan "$DEST/workflow.yaml" \
  --workdir "$DEST/.simpleworkflow"
```

O plano deve começar em `jedi00_prepare` e terminar em `jedi18_gate`.

Ele deve conter cross-cycle edges reais. Em especial:

```text
jedi06_prepare <- mpas00_gate + obs06_gate
jedi12_prepare <- mpas06_gate + obs12_gate
jedi18_prepare <- mpas12_gate + obs18_gate
```

Não deve existir nenhuma tarefa com prefixo `obs00_` ou `mpas18_`.

## 4. Dry-run de artifacts e comandos

Antes de qualquer `qsub`, execute:

```bash
swf run "$DEST/workflow.yaml" \
  --workdir "$DEST/.simpleworkflow" \
  --dry-run
```

O dry-run deve resolver todos os inputs iniciais e aceitar como futuros inputs apenas outputs declarados de dependências anteriores.

Qualquer `invalid-input`, referência ao runtime corrected antigo ou caminho para produto científico 06/12/18 da campanha de referência bloqueia a execução real.

## 5. Preflight dos contratos de domínio

Antes do `swf run` real, rode pelo menos o doctor inicial diretamente no novo case:

```bash
monan-jedi-workflow cycle-doctor "$DEST" \
  --cycle 2018-04-15T00:00:00Z \
  --no-observations
```

O ciclo inicial não possui `Obs2IODA00` na DAG; suas observações são starting inputs. Os doctors Obs2IODA06/12/18 fazem parte da própria DAG e verificam também as dependências compartilhadas do converter via `ldd`.

## 6. Execução real

Somente após `plan`, `--dry-run` e preflight passarem:

```bash
swf run "$DEST/workflow.yaml" \
  --workdir "$DEST/.simpleworkflow"
```

O `simpleWorkflow` executa as tarefas em ordem de dependência. Os comandos de domínio continuam responsáveis por PBS e validação científica.

Um downstream só atravessa um `*_gate` quando o manifest correspondente contém literalmente:

```json
{"valid": true}
```

O término do PBS, isoladamente, não libera o próximo stage.

## 7. Restart

Após uma interrupção, use o mesmo comando `swf run` e o mesmo `--workdir`. O simpleWorkflow reaproveita tarefas bem-sucedidas apenas quando assinatura e outputs continuam coerentes. Os gates usam fingerprint SHA-256 do manifest de validação, portanto uma mudança nesse manifest força nova avaliação do gate.

Não use `--force` ou `--resubmit` como procedimento normal de restart.

## 8. Critério de sucesso da rodada

A rodada por simpleWorkflow será aceita quando:

- `jedi18_gate` terminar com sucesso;
- todos os validation manifests JEDI/MPAS/Obs2IODA do replay tiverem `valid=true`;
- todos os JEDI repetirem o contrato temporal 18 physical = 18 logical steps e 21600 s;
- MPAS produzir os pares 03/06, 09/12 e 15/18 no novo namespace;
- JEDI06/12/18 consumir exclusivamente esses novos estados e os novos IODA06/12/18;
- complete-state preservation e sanidade numérica forem novamente satisfeitas;
- nenhum produto 06/12/18 da campanha de referência tiver sido usado como input intermediário.

A igualdade bitwise com a campanha de referência é diagnóstica, não requisito inicial de sucesso.
