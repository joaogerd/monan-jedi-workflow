# Instalação e configuração

## Pré-requisitos

No JACI, o usuário precisa ter acesso ao workspace do projeto e aos comandos básicos:

- `bash`;
- `git`;
- `module`;
- `anaconda` via módulo do JACI;
- `start_conda`;
- `qsub` e `qstat`;
- `mpiexec`;
- Python 3 via Anaconda;
- futuramente, executáveis MPAS-JEDI compilados.

## Clonar o repositório

```bash
cd /p/projetos/monan_das/$USER/projects
git clone https://github.com/joaogerd/monan-jedi-workflow.git
cd monan-jedi-workflow
```

## Configurar o site JACI

Crie uma configuração local:

```bash
cp configs/sites/jaci/site.env.example configs/sites/jaci/site.env
vi configs/sites/jaci/site.env
```

O arquivo `site.env` deve definir, ou herdar, variáveis como:

```bash
MONAN_WORKFLOW_ROOT
MONAN_DATA_ROOT
MONAN_EXTERNAL_DATA_ROOT
MONAN_SCRATCH
MONAN_QUEUE
MPAS_BUNDLE_BUILD
MPASJEDI_VARIATIONAL_EXE
MPI_LAUNCHER
```

## Carregar o ambiente

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
```

Esse comando carrega o módulo Anaconda, chama `start_conda`, define paths do workflow e exibe os principais valores detectados.

## Validar o ambiente

```bash
bash scripts/setup/check_runtime.sh configs/sites/jaci/site.env
```

Warnings sobre dados ausentes ou executáveis MPAS-JEDI ainda não configurados são esperados antes da primeira execução real.

## Validar a estrutura do projeto

```bash
bash tests/smoke_check.sh
```

Esse teste executa validações estruturais, renderizações em modo seguro e checagens de consistência dos manifestos.

## Preparar a árvore de dados

```bash
bash scripts/setup/bootstrap_3dvar_fgat_data_layout.sh
bash scripts/setup/create_3dvar_fgat_external_tree.sh
```

O primeiro comando cria a estrutura interna em `MONAN_DATA_ROOT`. O segundo cria a estrutura externa onde os arquivos reais serão colocados antes do staging.

## Validar o build MPAS-JEDI

Enquanto o build real não existir, use:

```bash
bash scripts/setup/find_mpas_jedi_build.sh --max-depth 7 ${MONAN_JACI_WORKSPACE}/projects
```

Quando o build existir, configure `MPAS_BUNDLE_BUILD` no `site.env` e rode:

```bash
bash scripts/setup/check_mpas_jedi_build.sh --strict
```
