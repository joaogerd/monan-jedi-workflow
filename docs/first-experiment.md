# Primeiro experimento científico na JACI — execução pelo simpleWorkflow

Esta é a receita de referência instalada em `catalog/reference-20250901/`: malha
x1.10242 (~240 km), 55 níveis, 128 ranks MPI, B correspondente, 3D-FGAT,
01/09/2025 às 00Z e 06Z. **A equivalência numérica na JACI continua pendente.**

## 1. Arquitetura e ambiente

**Não execute `qsub run-case.pbs`.** O pré-configurador não gera mais um job
monolítico. O **simpleWorkflow**, iniciado no login da JACI, é o controlador: executa
`prepare`/`validate` localmente e submete **cada etapa `run` necessária em
seu próprio job PBS**. Os aplicativos científicos não submetem outro PBS.

Na JACI, os compute nodes não veem `$HOME`. O Python que executará o worker,
o pacote `monan_jedi_workflow`, os executáveis e os dados científicos precisam
estar em filesystem acessível aos compute nodes, preferencialmente em `/p`.

No login, com ambiente MONAN-JEDI ativo:

```bash
command -v python
command -v swf
command -v monan-jedi-workflow
python -c 'import sysconfig; print(sysconfig.get_path("scripts"))'
```

O diretório retornado por `sysconfig` deve existir nos nós de computação.
O pré-configurador aceita `--runtime-bin /p/.../bin` para indicar explicitamente
um ambiente compartilhado. Ele **não instala** nem copia um ambiente Python.
Se o ambiente ativo estiver em `/home` ou `/home2`, mova/recrie o ambiente
em `/p` antes da criação; a geração recusa esse caminho como runtime padrão.

## 2. Configure as entradas do experimento

Estas variáveis apontam para a instalação **real** e para os dados científicos.
Confira os diretórios antes de seguir. Elas não são baixadas pelo gerador:

```bash
export STACK_ROOT=/p/projetos/monan_das/joao.gerd/work/spack-stack-inpe-overlay-20260515T181917Z/spack-stack
export MONAN_JEDI_INSTALL_ROOT=/p/projetos/monan_das/$USER/build/monan-jedi
export MONAN_MESH_ROOT=/p/projetos/monan_das/share/MONAN-JEDI-Data/meshes/quasi_uniform/x1.10242_240km
export MONAN_PHYSICS_ROOT=/p/projetos/monan_das/share/MONAN-JEDI-Data/physics/mpas/files
export MONAN_BMATRIX_ROOT=/p/projetos/monan_das/share/MONAN-JEDI-Data/covariance/x1.10242_240km/55levels
export MONAN_LIBFABRIC_ROOT=/opt/cray/libfabric/1.22.0/lib64
export MONAN_INPUT_ROOT=/p/projetos/monan_das/$USER/external-inputs
export MONAN_GFS_ROOT=/p/projetos/monan_das/$USER/data/gfs
```

São necessários o manifesto da instalação, mesh/invariant, partição de 128
ranks, tabela de física, matriz B, GFS 31/08/2025 18Z, PREPBUFR e GNSS-RO
01/09/2025 00Z e 06Z. Consulte as tabelas do catálogo e verifique
**existência, formato e horários**, não apenas diretórios.

## 3. Crie um NOVO experimento em /p

`NEW_CASE` é uma variável que contém o diretório novo que será criado; não é
um parâmetro automático da plataforma. O destino **não pode existir**.

```bash
export NEW_CASE=/p/projetos/monan_das/joao.gerd/work/first-experiment-20250901-swf
python -m monan_jedi_workflow.experiment_start "$NEW_CASE"
cd "$NEW_CASE"
ls experiment.yaml initialization.yaml init.yaml campaign.yaml environment.sh run-worker.sh
```

O gerador copia as configurações científicas para `science/`, cria os links dos
backgrounds, `environment.sh` com as exportações científicas, e `run-worker.sh`,
que prepara o `PATH` dentro de cada job PBS. O gerador verifica caminhos
candidatos conhecidos antes de utilizá-los; caminhos não encontrados exigem
configuração explícita. Se houver um carregador JACI institucional existente,
ele poderá ser usado pelos workers PBS. Um carregador que alterar `STACK_ROOT`
para um stack diferente da receita será rejeitado pelo worker.
**Não gera nem submete `run-case.pbs`.** A fila e o walltime do MPAS podem ser
configurados antes da criação por `--pbs-queue` e `--pbs-walltime` (padrão:
`pesqmidi` e `01:00:00` neste ensaio; confirme a política PBS atual).

## 4. Carregue o ambiente, confira os caminhos e exporte a campanha

```bash
source ./environment.sh
```

Se aparecer `[CONFIGURACAO]`, a mensagem indicará a variável ausente ou o
diretório inexistente. Corrija o caminho com `export NOME=/p/...` **antes de
carregar novamente** `environment.sh`. Nunca substitua por um caminho fictício
para contornar a verificação. Para consultar os valores resolvidos:

```bash
for var in MONAN_JEDI_INSTALL_ROOT STACK_ROOT MONAN_MESH_ROOT MONAN_PHYSICS_ROOT MONAN_BMATRIX_ROOT MONAN_INPUT_ROOT MONAN_GFS_ROOT MONAN_LIBFABRIC_ROOT; do
  printf '%s=%s\n' "$var" "${!var:-NAO_CONFIGURADO}"
done
```

Apenas depois que o ambiente carregar sem erros, prossiga.

```bash
campaign inspect campaign.yaml
campaign check campaign.yaml
campaign export campaign.yaml --engine simpleworkflow
swf validate workflow.yaml
swf plan workflow.yaml
```

A campanha gerada declara:

- Inicialização **uma vez**: WPS 31/08 18Z → MPAS Init → previsão MPAS inicial.
- 01/09 00Z: Obs2IODA → JEDI → previsão MPAS.
- 01/09 06Z: Obs2IODA → JEDI, sem previsão após a segunda análise.

O `simpleWorkflow` recebe tarefas `prepare/run/validate` com dependências
explícitas **dentro de cada fase**. A inicialização inteira é executada primeiro
em seu próprio motor; só depois de concluída com sucesso o motor dos ciclos
começa 00Z. Não é necessário nem válido referenciar o nome de uma tarefa de
inicialização em `depends_on` de uma tarefa de ciclo.
WPS, MPAS, Obs2IODA e JEDI têm jobs PBS individuais para a etapa `run`,
e as demais operações são tarefas locais de controle. O wrapper do worker
confere a acessibilidade do Python e das CLIs no compute node antes de executar.

`campaign check` verifica a estrutura do plano; não substitui a conferência dos
dados reais, o `swf validate` ou a aceitação científica dos resultados.

### Para um experimento já criado antes da geração do ambiente

**Não apague nem recrie o experimento atual.** Depois de atualizar o checkout
do repositório com `git pull --ff-only`, execute no login:

```bash
python -m monan_jedi_workflow.experiment_start "$NEW_CASE" --configure-existing
cd "$NEW_CASE"
source ./environment.sh
```

Esse modo cria somente `environment.sh` e adiciona sua importação ao
`run-worker.sh` existente. Ele não modifica `science/`, `experiment.yaml`,
`campaign.yaml` ou os backgrounds. Se `environment.sh` já existir, a operação
é recusada para proteger ajustes feitos pelo usuário.

## 5. Execute SOMENTE pelo orquestrador

```bash
swf run workflow.yaml --ui plain
```

Execute esse comando no login com o ambiente controlador configurado. **Não
submeta o `swf run` dentro de outro job PBS.** Cada operação com
`executor: pbs` é submetida individualmente pelo simpleWorkflow.
O motor registra job ID, logs, tentativas, dependências e estado final.

A execução nunca deve reutilizar saídas científicas de outro caso para
satisfazer uma dependência. O MPAS inicial produz os estados que alimentam JEDI
00Z; o MPAS 00Z produz a trajetória de 03Z e o estado de 06Z para JEDI 06Z.

## 6. Verificação posterior

```bash
swf status workflow.yaml
jedi status experiment.yaml --cycle 2025-09-01T00:00:00Z
jedi status experiment.yaml --cycle 2025-09-01T06:00:00Z
```

Conferir `work/`, saídas de JEDI e MPAS, IODA de ambos os horários e logs em
`.simpleworkflow/runs/`. Para equivalência numérica exata com a campanha
histórica, seguir `docs/validation/2025-reference-scientific-validation.md`.

**Status:** integração do grafo e gerador implementada no branch beta; o
comportamento real em compute nodes da JACI **ainda precisa ser validado**.
Não declarar validação científica antes da execução bem-sucedida e da
comparação de produtos.
