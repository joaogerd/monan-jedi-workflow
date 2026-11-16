# Primeiro experimento científico na JACI — controlador Python no login

**Contrato obrigatório:** O `simpleWorkflow` executa tarefas `executor: local`
no **nó de login** e invoca os aplicativos Python MONAN-JEDI. Os aplicativos
`jedi`, `mpas`, `mpas init`, `wps` e `obs convert` preparam seus próprios
comandos científicos; quando a etapa precisa de recursos, **o aplicativo chama
`qsub` do login e espera o fim**. Nos nós de computação executam-se **somente
scripts shell e binários científicos**, sem Conda ou CLIs Python.

O ambiente Conda pode permanecer em `/h2mnt/home`, pois não é usado nos
nós de computação. Os diretórios científicos, binários e arquivos de
execução devem estar em `/p` ou outro filesystem acessível aos compute nodes.

## 1. Preparação do ambiente

No login, ative o Conda `monan-jedi` e carregue as variáveis do experimento:

```bash
cd "$NEW_CASE"
source ./environment.sh
```

Esse arquivo valida as âncoras: `MONAN_JEDI_INSTALL_ROOT`, `STACK_ROOT`,
`MONAN_MESH_ROOT`, `MONAN_PHYSICS_ROOT`, `MONAN_BMATRIX_ROOT`,
`MONAN_INPUT_ROOT`, `MONAN_GFS_ROOT`, `MONAN_LIBFABRIC_ROOT`.

Os caminhos devem existir, mas isso não comprova a presença de todos os
arquivos científicos. Confirme o GFS 31/08/2025 18Z, PREPBUFR e GNSS-RO
01/09/2025 00Z/06Z, malha x1.10242, partição 128 ranks, física, matriz B,
manifesto do runtime e binários MPAS/JEDI/WPS/Obs2IODA.

## 2. Gerar caso novo (sem sobrescrever arquivos)

```bash
export NEW_CASE=/p/projetos/monan_das/joao.gerd/work/first-experiment-20250901-login
python -m monan_jedi_workflow.experiment_start "$NEW_CASE"
cd "$NEW_CASE"
source ./environment.sh
```

O gerador produz `science/`, `experiment.yaml`, `initialization.yaml`,
`init.yaml`, `campaign.yaml` e `environment.sh`. Um eventual
`run-worker.sh` é apenas um artefato de compatibilidade: **não está presente
nas tarefas exportadas para o simpleWorkflow**.

A campanha contém 9 tarefas de inicialização (WPS, MPAS Init e MPAS inicial),
e 15 tarefas nos ciclos 00Z e 06Z. Cada etapa científica tem tarefas
`prepare/run/validate`; todas são executadas pelo controlador no login,
com submissão PBS nativa dentro da operação `run` quando configurada.

## 3. Adaptar com segurança o caso já criado

Se o experimento já tem `campaign.yaml`, `workflow.yaml` e
`environment.sh`, **não apague nem recrie**:

```bash
cd /p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow
git pull --ff-only
cd "$NEW_CASE"
source ./environment.sh
python -m monan_jedi_workflow.experiment_start "$NEW_CASE" --upgrade-existing
campaign check campaign-login.yaml
campaign export campaign-login.yaml --engine simpleworkflow
swf validate workflow-login.yaml
swf plan workflow-login.yaml
```

A migração salva a configuração WPS anterior, se precisar modificá-la,
adiciona recursos PBS à etapa científica `wps.run`, cria
`campaign-login.yaml` e exporta **um novo** `workflow-login.yaml`. Não
sobrescreve `workflow.yaml`, que pode ainda conter submissões Python
diretamente ao PBS e **não deve ser executado**. A migração recusa reuso
silencioso se a campanha nova já existir.

## 4. Arquitetura esperada do plano

```text
simpleWorkflow (login; todos os seus tasks são executor: local)
  WPS prepare        [Python login: GRIB/namelist]
  WPS run            [Python login: qsub shell link_grib/ungrib]
  WPS validate       [Python login]
  MPAS Init prepare  [Python login: gera PBS]
  MPAS Init run      [Python login: qsub PBS científico, espera]
  MPAS Init validate [Python login]
  MPAS inicial       [mesma sequência]
  OBS 00Z            [Python login: prepara, qsub conversores, valida]
  JEDI 00Z           [Python login: prepara, qsub PBS, valida]
  MPAS 00Z           [Python login: prepara, qsub PBS, valida]
  OBS 06Z            [Python login: prepara, qsub conversores, valida]
  JEDI 06Z           [Python login: prepara, qsub PBS, valida]
```

Os scripts PBS contêm binários científicos e shell, não `python`,
`monan-jedi-workflow`, `obs`, `mpas` ou `jedi` como CLIs Python.
A inicialização é uma fase distinta no simpleWorkflow; os ciclos só
começam depois que ela termina com sucesso.

O aplicativo da etapa acompanha o job e não declara sucesso científico
antes da validação de logs/produtos. O `simpleWorkflow` registra estado,
dependências, tentativas e saídas dos comandos de controle.

## 5. Antes da primeira submissão

```bash
swf validate workflow-login.yaml
swf plan workflow-login.yaml
python - <<'PY'
import yaml
wf = yaml.safe_load(open('workflow-login.yaml'))
tasks = wf['initialization']['tasks'] + wf['tasks']
wrong = [task['name'] for task in tasks if task.get('executor') != 'local' or 'pbs' in task]
if wrong:
    raise SystemExit('ERRO: tarefas nao locais: ' + ', '.join(wrong))
print('[OK] Todas as 24 tarefas sao aplicativos executados no login.')
PY
```

A validação estrutural não prova a existência de todos os dados ou o sucesso
do PBS científico. Apenas depois do preflight completo, execute **no login**
`swf run workflow-login.yaml --ui plain`.

## 6. Verificação

Use `swf status workflow-login.yaml`, logs científicos em `work/`,
manifests por aplicação e arquivos PBS nativos. A comparação científica
com a referência histórica continua **pendente**. A integração atualizada
ainda precisa de teste de execução real na JACI.
