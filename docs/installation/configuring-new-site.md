# Configurar um novo site computacional

> **Contrato v1 (25/11/2026).** Este guia documenta o caminho **operacional e validado na JACI com PBS**. Perfis `local` e `slurm` podem ser validados estruturalmente, **mas a execução científica com esses backends ainda não está implementada**. Não confunda a aprovação do perfil com a homologação de uma nova máquina.

## 1. Responsabilidades: máquina, ciência e campanha

- **`machine.yaml`** descreve *onde* ficam instalações e catálogos, *como* inicializar o ambiente e *quais* recursos PBS utilizar. O campo `machine.name` é apenas um identificador; o código não deve decidir caminhos pela palavra `jaci`.
- **Receita científica** define a seleção de malha/resolução, matriz B, níveis, física, método de assimilação e observações. `paths.mesh_root` e `paths.bmatrix_root` apontam para recursos disponíveis e, na ponte de compatibilidade atual, são exportados como variáveis do ambiente; não constituem uma seleção científica genérica.
- **`campaign.yaml`** define calendário e operações. Os produtos e o estado de uma campanha são privados de seu diretório.

Não reutilize a configuração científica de 240 km/55 níveis em outra resolução apenas porque os caminhos existem. A receita distribuída e homologada é `mpas-jedi-3dvar` na configuração de referência; outras resoluções exigem perfis científicos completos.

## 2. Pré-requisitos do ambiente PBS atualmente suportado

1. Checkout ou instalação funcional do `monan-jedi-workflow` e do controlador `simpleWorkflow`, com comandos `experiment` disponíveis no nó de login.
2. Instalação científica MONAN-JEDI/MPAS que publique `share/monan-jedi/install-manifest.json` com **contrato de runtime v2**; Spack-stack e módulos compatíveis com esse manifesto.
3. Acesso de leitura a malha, partições, física, matriz B, GFS e observações das datas escolhidas; acesso de escrita a um diretório novo de experimento.
4. PBS com filas e recursos verificados **no site real**, incluindo executável MPI compatível. Não presuma `/opt/cray`, filas da JACI ou 128 CPUs em outro cluster.
5. Capacidade de carregar no job PBS as bibliotecas científicas usadas pelos executáveis; `--check-paths` não verifica a compatibilidade de binários ou módulos.

A execução observada na JACI em 25/11/2026 aprovou **24/24 tarefas** (9 de inicialização, 15 da campanha de duas análises); a comparação numérica entre produtos e baseline científico permanece uma verificação separada.

## 3. Criar `machine.yaml` sem alterar o legado

Comece por copiar o **exemplo**, não o `site.yaml` legado. O exemplo contém placeholders e **não** é um perfil operacional.

```bash
# No checkout do repositório:
mkdir -p "$HOME/.config/monan-jedi"
cp configs/sites/jaci/machine.yaml.example \
  "$HOME/.config/monan-jedi/machine.yaml"
# Edite o arquivo, substituindo TODOS os caminhos, filas e recursos pelos da sua máquina.
${EDITOR:-vi} "$HOME/.config/monan-jedi/machine.yaml"
```

Para um cluster PBS, a estrutura **mínima para criação de um caso científico** inclui todos os diretórios obrigatórios na ponte v1, `environment.kind: modules`, um script de setup e políticas completas para os cinco estágios. Exemplo ilustrativo (substitua cada caminho e recurso; nunca use diretamente para submeter jobs):

```yaml
schema_version: 1
machine:
  name: cluster-exemplo
paths:
  work_root: /dados/projeto/usuario
  installation_root: /instalacoes/monan-jedi
  stack_root: /instalacoes/spack-stack
  mesh_root: /dados/meshes
  physics_root: /dados/physics
  bmatrix_root: /dados/covariance
  observations_root: /dados/observations
  gfs_root: /dados/gfs
  libfabric_root: /instalacoes/libfabric/lib64
execution:
  backend: pbs
  stages:
    jedi:      {queue: fila-cpu, walltime: '01:00:00', select: 1, ncpus: 32, mpiprocs: 32, launcher: /usr/bin/mpiexec}
    mpas:      {queue: fila-cpu, walltime: '02:00:00', select: 1, ncpus: 32, mpiprocs: 32, launcher: /usr/bin/mpiexec}
    mpas_init: {queue: fila-cpu, walltime: '01:00:00', select: 1, ncpus: 32, mpiprocs: 32, launcher: /usr/bin/mpiexec}
    wps:       {queue: fila-cpu, walltime: '01:00:00', select: 1, ncpus: 1, mpiprocs: 1}
    obs2ioda:  {queue: fila-cpu, walltime: '01:00:00', select: 1, ncpus: 1, mpiprocs: 1}
environment:
  kind: modules
  setup: /instalacoes/spack-stack/site/setup.sh
```

**Atenção:** os valores `ncpus`, `mpiprocs`, `select` e o launcher são apenas demonstrativos. O gerador v1 ainda precisa ser confrontado com a receita científica: as partições MPAS e suas quantidades de ranks podem estar fixadas no perfil científico escolhido. Não reduza os ranks do perfil sem verificar essas dependências. `environment.setup` também precisa coincidir com o `site_setup` publicado no manifesto de instalação v2; apenas a existência do arquivo não basta.

### Campos e validações

| Campo | Contrato v1 |
| --- | --- |
| `schema_version` | Inteiro `1` |
| `machine.name` | Identificador simples, obrigatório |
| `paths.work_root` | Diretório absoluto obrigatório |
| `paths.scratch_root` | Opcional |
| `paths.installation_root`, `stack_root`, `mesh_root`, `physics_root`, `bmatrix_root`, `observations_root`, `gfs_root`, `libfabric_root` | Obrigatórios para `experiment create --machine` com PBS; opcionais na inspeção estrutural |
| `execution.backend` | `pbs`, `slurm` ou `local`; somente `pbs` cria caso científico atualmente |
| `execution.stages` | `jedi`, `mpas`, `mpas_init`, `wps`, `obs2ioda` obrigatórios no PBS; `mpas_initial` opcional |
| `execution.stages.*` | `queue`, `walltime`, `select`, `ncpus`, `mpiprocs`; `launcher` também para JEDI, MPAS, MPAS-Init e MPAS inicial |
| `execution.queue_limits` | Opcional: limites máximos em minutos, por nome de fila; validar contra a configuração vigente do scheduler |
| `environment.kind` | `modules` obrigatório para criação PBS atual; `native` aceito para inspeção de perfil local |
| `environment.setup` | Script absoluto, obrigatório quando `kind: modules` |

A previsão atmosférica inicial usa `science/initialization/mpas.yaml`, cujo estágio padrão é **`mpas`**. Para recursos próprios, acrescente `execution.stages.mpas_initial`. Não confunda com `mpas_init`, que configura o executável `mpas_init_atmosphere`.

## 4. Validar o perfil **antes** da criação

Use o módulo do checkout para evitar misturar o código em desenvolvimento com uma instalação Conda antiga:

```bash
MACHINE="$HOME/.config/monan-jedi/machine.yaml"
python -m monan_jedi_workflow.unified_cli experiment machine validate "$MACHINE"
python -m monan_jedi_workflow.unified_cli experiment machine validate "$MACHINE" --check-paths
python -m monan_jedi_workflow.unified_cli experiment machine show "$MACHINE"
```

- A primeira validação verifica o **schema**; pode passar sem instalações científicas.
- `--check-paths` verifica os **diretórios declarados** e o arquivo `environment.setup`; não verifica filas, bibliotecas ou produtos.
- A criação com `--machine` verifica adicionalmente o contrato de runtime v2, sua associação ao setup e a política completa dos estágios PBS.

Se houver erro, corrija o **perfil real**. Não altere dados científicos nem escolha caminhos fictícios apenas para passar na validação.

## 5. Criar um caso novo e isolado

Escolha uma data com GFS de inicialização e observações disponíveis. A data a seguir é somente um **caso de referência**, não uma data universal:

```bash
MACHINE="$HOME/.config/monan-jedi/machine.yaml"
CASE="/diretorio-gravavel/experiments/primeiro-teste"
test ! -e "$CASE" || { echo "O caso ja existe; nao sobrescrever"; exit 1; }

python -m monan_jedi_workflow.unified_cli experiment create "$CASE" \
  --machine "$MACHINE" \
  --start 2026-01-30T00:00:00Z

cd "$CASE"
ls -l machine-profile-lock.yaml environment.sh campaign.yaml science/site.yaml
source ./environment.sh
```

A nova rota `--machine` **não** pode ser combinada com `--site`, `--workspace`, `--pbs-queue` ou `--pbs-walltime`; os recursos vêm de `execution.stages`. O `machine-profile-lock.yaml` registra o perfil resolvido utilizado na criação. Não modifique arquivos de uma campanha já iniciada para trocar o site.

## 6. Aceitação sem consumir recursos

```bash
experiment check campaign.yaml
experiment export campaign.yaml
experiment validate workflow.yaml
experiment plan workflow.yaml
experiment check-inputs .
```

`experiment export` escreve o `workflow.yaml`; execute uma vez no caso novo. Confirme também os recursos dos YAMLs científicos, incluindo `science/initialization/mpas_init.yaml` versus `science/initialization/mpas.yaml`, e compare o launcher com a instalação real. Inspecione ainda as entradas GFS/observações, a matriz B, as partições da malha, o acesso às filas e a disponibilidade de bibliotecas no **compute node**.

Os três grupos esperados na receita de duas análises são inicialização WPS/MPAS, observações+JEDI+MPAS em 00 UTC, e observações+JEDI em 06 UTC (9 + 15 tarefas). O texto `[local]` do `simpleWorkflow` descreve as tarefas do controlador; não demonstra que MPAS/JEDI rodaram no login.

## 7. Execução controlada e verificação científica

**Os próximos comandos podem submeter jobs PBS e consumir recursos.** Só os execute em um caso novo, depois de aprovar os testes anteriores e os limites reais das filas.

```bash
cd "$CASE"
source ./environment.sh
set -o pipefail
experiment run workflow.yaml --ui plain 2>&1 | tee run.log
experiment status workflow.yaml
```

A aprovação de todas as tarefas confirma os contratos de execução e validação dos estágios. Para homologar cientificamente um novo site, preserve logs PBS, IDs dos jobs, manifests, hashes e compare os produtos NetCDF/IODA, horários, estados MPAS, evolução da função custo e diagnósticos de observações (O-B/O-A e QC) com a referência. A comparação numérica pode exigir tolerâncias documentadas entre arquiteturas.

**Nunca apague `.simpleworkflow/`, `work/`, manifests ou scripts PBS para tentar corrigir uma falha.** Use `experiment status workflow.yaml` e `diagnose . --no-pbs` primeiro; verifique a situação do scheduler antes de considerar uma retomada. Não execute uma segunda instância de `experiment run` enquanto a primeira ainda estiver ativa.

## 8. Ambientes locais, Slurm e compatibilidade

O exemplo `configs/sites/local/machine.yaml.example` é válido para testes **estruturais**. Hoje, `experiment create --machine` rejeita `local` e `slurm` explicitamente: não há fallback silencioso para PBS. A implementação real desses executores pertence à fase posterior da refatoração.

O formato legado `site.yaml` continua suportado por `experiment create --site` e pelo fluxo anterior de workspace, mas **não** deve ser utilizado como substituto de `machine.yaml`. A ponte entre os contratos existe para preservar a execução PBS durante a migração.

## 9. Diagnóstico resumido

| Sintoma | Verificação |
| --- | --- |
| `Machine profile not found` | Substituir caminhos demonstrativos por um arquivo `machine.yaml` realmente criado |
| `--check-paths` falha | Corrigir diretórios absolutos ou `environment.setup` |
| Erro de manifesto/stack | Conferir instalação `install-manifest.json` v2 e o setup declarado |
| Erro `execution.stages` | Preencher todos os recursos dos cinco estágios obrigatórios; revisar os limites das filas |
| Backend `local` ou `slurm` rejeitado no `create` | Limitação deliberada da versão atual, não um defeito da validação |
| `experiment check-inputs` falha | Confirmar GFS e observações **na data do ciclo**, sem reutilização silenciosa |
| `ncdump` ausente | Na inspeção padrão `ncdump -h`, Obs2IODA pode usar o fallback `monan_jedi_workflow.ioda_header` via `netCDF4`; verificar a versão do pacote carregado |
| Um estágio falha após `run` | Preservar estado e logs; executar `experiment status` e `diagnose`, sem reset |

## 10. Critério de conclusão da implantação

Um site PBS só pode ser declarado operacional quando: o perfil válido está versionado ou arquivado de forma reprodutível; o runtime v2 e os estágios são compatíveis; um caso isolado passa por check/export/validate/plan/check-inputs/run/status; os 24 estados do caso de referência estão `SUCCESS`; e a comparação dos produtos científicos com o baseline foi analisada e registrada.

**Referências:** [contrato técnico v1](../developer/machine-profiles.md), [tutorial operacional](../tutorial.md), [arquitetura](../developer/architecture.md).
