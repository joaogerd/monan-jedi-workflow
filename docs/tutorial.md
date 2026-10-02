# Tutorial — do zero a uma campanha MONAN-JEDI

Este é o caminho normal do usuário. Não é necessário procurar outros exemplos.

## 1. O que você precisa

A campanha usa três componentes:

- **MONAN-JEDI**: runtime científico instalado, incluindo MONAN/MPAS,
  MPAS-JEDI e Obs2IODA;
- **simpleWorkflow**: orquestrador que executa e acompanha as tarefas;
- **monan-jedi-workflow**: interface que transforma a configuração científica
  da campanha em um workflow executável.

Você também precisa de acesso aos dados científicos do experimento. As seções
abaixo mostram a ordem correta de preparação no JACI.

## 2. Comece em um shell JACI limpo

Não reutilize um shell no qual outro ambiente Conda, outro spack-stack ou outra
instalação MONAN-JEDI já tenha sido carregada. Misturar ambientes pode fazer o
Python do Conda importar bibliotecas Python vindas do spack-stack, o que torna
erros difíceis de diagnosticar.

### 2.1 Torne o Conda disponível

Em cada novo login no JACI:

```bash
module load anaconda
start_conda
```

### 2.2 Crie o ambiente Python uma única vez

Na primeira instalação:

```bash
conda create -n monan-jedi -c conda-forge \
  python=3.11 pip \
  pyyaml numpy=1.26 netcdf4 cftime xarray matplotlib \
  esmpy windspharm pytest ruff -y

conda activate monan-jedi
```

A criação do ambiente é feita **uma única vez**.

Nos logins seguintes, não recrie o ambiente. Apenas inicialize o Conda no shell
novo e ative o ambiente existente:

```bash
module load anaconda
start_conda
conda activate monan-jedi
```

A sequência `module load anaconda` + `start_conda` precisa ser repetida em
um shell JACI novo; `conda create` não.

Para a estratégia completa de isolamento entre Conda e spack-stack, incluindo
diagnóstico de mistura de NumPy/Python, veja também
[Installation on JACI no MPAS-BMatrix](https://github.com/joaogerd/MPAS-BMatrix/blob/main/docs/install-jaci.md).

### Checkpoint 1 — ambiente Python

Execute:

```bash
command -v python

python -c "import sys, numpy; \
print(sys.version); \
print(sys.executable); \
print(numpy.__file__)"
```

O resultado esperado é:

- Python 3.11;
- `sys.executable` dentro do ambiente `monan-jedi`;
- NumPy carregado do mesmo ambiente Conda;
- nenhum NumPy vindo de `spack-stack/.../site-packages`.

Uma verificação adicional útil é:

```bash
printf 'CONDA_PREFIX=%s\n' "$CONDA_PREFIX"
printf 'PYTHONPATH=%s\n' "${PYTHONPATH:-<not set>}"
```

Neste ponto, o Python e o NumPy devem resolver abaixo de `$CONDA_PREFIX`.
O spack-stack científico será carregado somente depois que esse checkpoint
estiver correto.

### 2.3 Instale os comandos Python

Com `monan-jedi` ativo, instale o simpleWorkflow e esta interface:

```bash
pip install simpleworkflow

git clone https://github.com/joaogerd/monan-jedi-workflow.git
cd monan-jedi-workflow
python -m pip install -e .
```

Se o repositório já existir, não o clone novamente. Entre no checkout correto e
instale-o com `python -m pip install -e .`.

Verifique:

```bash
command -v swf
command -v monan-jedi-workflow
swf --help
monan-jedi-workflow --help
```

Os dois comandos devem resolver dentro do mesmo ambiente Conda ativo.

### 2.4 Selecione o runtime científico MONAN-JEDI

Defina as duas âncoras públicas do ecossistema:

```bash
export MONAN_JEDI_INSTALL_ROOT=/caminho/para/monan-jedi-instalado
export STACK_ROOT=/caminho/para/spack-stack-validado
```

O `MONAN_JEDI_INSTALL_ROOT` deve apontar para uma instalação MONAN-JEDI que
contenha:

```text
bin/
share/monan-jedi/install-manifest.json
```

O `STACK_ROOT` deve apontar para o spack-stack usado por essa instalação.

O workflow lê o manifesto instalado para descobrir o ambiente científico. Não
copie caminhos internos do spack-stack para os YAMLs do caso.

### Checkpoint 2 — comandos e runtime

Execute:

```bash
test -f "$MONAN_JEDI_INSTALL_ROOT/share/monan-jedi/install-manifest.json"

command -v python
command -v swf
command -v monan-jedi-workflow

python -c "import sys, numpy; print(sys.executable); print(numpy.__file__)"
```

Esperado:

- Python, `swf` e `monan-jedi-workflow` pertencem ao ambiente Conda
  `monan-jedi`;
- NumPy também vem desse ambiente;
- o manifesto MONAN-JEDI instalado existe;
- `MONAN_JEDI_INSTALL_ROOT` e `STACK_ROOT` estão definidos.

## 3. Caso de referência 2025 fornecido pelo repositório

O `examples/case/` não é mais um esqueleto abstrato. Ele representa o primeiro
caso de referência a validar no JACI:

```text
primeira análise : 2025-09-01 00Z
fim P3D          : 2025-09-04 00Z
cadência         : 6 h
malha            : x1.10242 (~240 km)
níveis           : 55
MPAS             : 128 MPI ranks
FGAT states      : 3 h
JEDI             : 3D-FGAT
observações      : GDAS PREPBUFR — radiossondas + superfície
```

A escolha de setembro de 2025 é intencional: os assets JACI usados pelo
MPAS-BMatrix apontam para o conjunto `mpasjedi_tutorial202509NCAR`, e o
PREPBUFR GDAS está disponível para o período.

### 3.1 Defina os dados do site

No JACI:

```bash
export MONAN_JEDI_DATA_ROOT=/p/projetos/monan_das/$USER/external-inputs

export MONAN_JEDI_MESH_ROOT=\
/p/projetos/monan_das/$USER/projects/mpas_meshes/quasi_uniform/x1.10242_240km

export MONAN_JEDI_BMATRIX_ROOT=/caminho/para/B_Matrix-x1.10242-validada

export MONAN_JEDI_GFS_ROOT=/p/projetos/monan_das/$USER/data/gfs

export MONAN_JEDI_WORKFLOW_ROOT=/caminho/para/monan-jedi-workflow
```

`MONAN_JEDI_BMATRIX_ROOT` deve apontar para a B x1.10242 já produzida e
validada. Não use uma B de outra malha/grade vertical.

### 3.2 Dados necessários para iniciar P3D

A inicialização da primeira análise começa seis horas antes, em
**2025-08-31 18Z**. O caso espera o GFS f000 em:

```text
$MONAN_JEDI_GFS_ROOT/2025083118/gfs.t18z.pgrb2.0p25.f000
```

E espera PREPBUFR para cada análise de 2025-09-01 00Z até
2025-09-04 00Z:

```text
$MONAN_JEDI_DATA_ROOT/observations/prepbufr/2025/
  prepbufr.gdas.20250901.t00z.nr.48h
  prepbufr.gdas.20250901.t06z.nr.48h
  ...
  prepbufr.gdas.20250904.t00z.nr.48h
```

O PREPBUFR é o produto GDAS/NCEP da coleção NSF NCAR GDEX d337000. O caso não
silencia arquivos ausentes: `campaign check` lista os ciclos que ainda
precisam ser staged.

### Checkpoint 3 — assets fixos

```bash
test -s "$MONAN_JEDI_DATA_ROOT/mpasjedi_tutorial202509NCAR/MPAS_namelist_stream_physics_files/x1.10242.invariant.nc"
test -s "$MONAN_JEDI_MESH_ROOT/partitions/x1.10242.graph.info.part.128"
test -s "$MONAN_JEDI_GFS_ROOT/2025083118/gfs.t18z.pgrb2.0p25.f000"
test -d "$MONAN_JEDI_BMATRIX_ROOT"
```

Todos devem terminar com status zero antes de iniciar a campanha.

## 4. Crie seu caso a partir do único template

Volte à raiz do checkout do `monan-jedi-workflow`. Copie o diretório inteiro:

```bash
cd /caminho/para/monan-jedi-workflow
cp -r examples/case my-experiment
cd my-experiment
```

Não copie YAMLs isoladamente e não procure outro exemplo. O diretório criado é
a configuração completa do usuário:

```text
my-experiment/
  campaign.yaml
  profile.yaml
  mpas.yaml
  obs2ioda.yaml
  jedi.yaml
  initialization/
    mpas.yaml
  templates/
    README.md
```

O `workflow.yaml` **não existe ainda e não deve ser escrito pelo usuário**.
Ele será produzido por `campaign create` depois que a configuração passar no
preflight.

### Checkpoint 3 — caso criado

```bash
pwd
find . -maxdepth 2 -type f | sort
```

Confirme que os arquivos acima existem. Neste momento vários campos contêm
`EDITAR`; isso é intencional. O preflight recusará executar o caso enquanto
qualquer placeholder `EDITAR` permanecer nos YAMLs ativos.

## 5. Entenda e ajuste o experimento, arquivo por arquivo

Não tente editar todos os YAMLs ao mesmo tempo. Siga esta ordem.

### 5.1 `campaign.yaml` — quando executar

Abra:

```bash
vi campaign.yaml
```

Para o primeiro experimento, defina:

```yaml
campaign:
  name: meu-experimento-3d
  start: AAAA-MM-DDT00:00:00Z
  duration: P3D
  cycle_interval_hours: 6
  destination: cases/meu-experimento-3d
```

Você precisa decidir somente o nome, a primeira análise, a duração e a cadência.
A data só pode ser escolhida depois de confirmar que inicialização e observações
existem para todo o período.

Não altere para P7D/P30D/P365D antes de validar P3D.

Referência completa: [configuração da campanha](configuration/campaign.md).

### Checkpoint 4 — período

```bash
grep -nE 'name:|start:|duration:|cycle_interval_hours:|destination:' campaign.yaml
```

Confirme que não há `EDITAR` nessas chaves e que o destination é novo.

### 5.2 `profile.yaml` — como os componentes se conectam

Para o layout padrão copiado de `examples/case`, normalmente mantenha:

```yaml
profile:
  cycling_jedi_case: .
  initial_mpas_case: initialization
  mpas_case: .
  obs2ioda_config: obs2ioda.yaml
```

Esses caminhos dizem ao materializador onde encontrar JEDI, forecast MPAS,
inicialização e Obs2IODA. Eles não definem a ciência.

Deixe `observation_acquisition.enabled: false` enquanto estiver fornecendo os
arquivos de observação manualmente. Habilite aquisição automática somente
quando os providers daquele período estiverem configurados e testados.

### Checkpoint 5 — ligação do caso

```bash
test -f jedi.yaml
test -f mpas.yaml
test -f initialization/mpas.yaml
test -f obs2ioda.yaml
```

Os quatro comandos devem terminar sem mensagem de erro.

### 5.3 `mpas.yaml` — forecast cíclico MONAN/MPAS

Abra:

```bash
vi mpas.yaml
```

Preencha, no mínimo:

1. `static_root`: onde estão invariant, partição e demais dados fixos;
2. `lead_hours`: horizonte de cada forecast;
3. `forecast_contract.da_state_interval_hours`: frequência do estado usado
   pela DA/FGAT;
4. `forecast_contract.mpi_ranks` e `partition`;
5. links do estado de análise, executável e arquivos estáticos;
6. namelist e streams em `templates/`;
7. fila, CPUs, ranks e walltime em `pbs`;
8. produtos esperados em `validation`.

Para o ciclo inicial de 6 h usado atualmente, `run_hours`, outputs, streams e
a cadência precisam ser coerentes entre si. Não escolha partição ou número de
ranks apenas copiando outro experimento.

Referência completa: [MONAN/MPAS](configuration/mpas.md).

### Checkpoint 6 — MPAS

```bash
grep -n 'EDITAR' mpas.yaml
```

Antes do preflight final, esse comando não deve retornar nenhuma linha.

### 5.4 `obs2ioda.yaml` — quais observações entram

Abra:

```bash
vi obs2ioda.yaml
```

Para **cada** família assimilada, declare:

```yaml
converters:
  - name: nome-do-conversor
    inputs:
      - caminho-do-dado-bruto
    outputs:
      - caminho-do-produto-IODA
    argv:
      - executavel-do-conversor
      - argumentos
```

A regra é importante:

```text
dado bruto -> conversor Obs2IODA -> output IODA -> link no JEDI -> observer
```

Se uma dessas ligações estiver ausente, a observação não está completamente
configurada.

Referência completa: [observações](configuration/observations.md).

### Checkpoint 7 — observações

```bash
grep -n 'EDITAR' obs2ioda.yaml
```

Além de não haver placeholders, confirme manualmente que os arquivos brutos
existem para **todos os ciclos** da campanha. O `campaign check` fará essa
verificação novamente usando as datas renderizadas.

### 5.5 `jedi.yaml` — assimilação

Abra:

```bash
vi jedi.yaml
```

Confira nesta ordem:

1. `cycle`: passo, offset do background e janela;
2. `bmatrix_root`: B compatível com a geometry/malha;
3. `background` e `analysis_base_state`;
4. um link para cada output IODA realmente usado;
5. `templates/variational.yaml`;
6. namelist MPAS-JEDI;
7. recursos PBS;
8. produto de análise esperado em `validation`.

O nome declarado em `analysis_base_state.target` e o produto esperado pelo
forecast seguinte precisam representar o **mesmo estado de análise**.

Referência completa: [JEDI](configuration/jedi.md).

### Checkpoint 8 — JEDI

```bash
grep -n 'EDITAR' jedi.yaml
```

Esse comando também deve terminar sem retornar linhas.

### 5.6 `initialization/mpas.yaml` — primeiro background

Este arquivo é diferente de `mpas.yaml`: ele prepara o estado que alimentará
a **primeira análise** da campanha.

Abra:

```bash
vi initialization/mpas.yaml
```

Defina o estado inicial, templates, recursos e outputs. A integração precisa
cobrir pelo menos um `cycle_interval_hours` antes da primeira análise.

O tutorial será completado com WPS + `mpas_init_atmosphere` no baseline 2025,
para que a origem desse primeiro estado também seja reproduzível e não uma
etapa manual escondida.

### Checkpoint 9 — inicialização

```bash
grep -n 'EDITAR' initialization/mpas.yaml
```

Não deve haver placeholders antes da execução.

### 5.7 `templates/` — arquivos científicos consumidos pelos executáveis

Leia primeiro:

```bash
cat templates/README.md
```

O caso real precisa fornecer os namelists, streams e `variational.yaml`
referenciados pelos YAMLs anteriores. Não use um template de outra malha ou
experimento sem verificar geometry, níveis, datas, B, observers e outputs.

### Checkpoint 10 — nenhum placeholder restante

Da raiz de `my-experiment`:

```bash
grep -RIn 'EDITAR' \
  campaign.yaml profile.yaml mpas.yaml obs2ioda.yaml jedi.yaml initialization templates
```

Para um caso pronto, o comando não deve retornar nenhuma configuração ativa
não resolvida.

## 6. Faça o preflight completo antes de executar

Da raiz do repositório:

```bash
monan-jedi-workflow campaign check my-experiment/campaign.yaml
```

Corrija tudo que aparecer como erro. Não prossiga enquanto o preflight não
estiver limpo.

## 7. Materialize sem submeter

```bash
monan-jedi-workflow campaign create my-experiment/campaign.yaml
```

O diretório indicado por `campaign.destination` será criado. Agora sim ele
conterá o `workflow.yaml`.

Inspecione:

```bash
swf plan CAMPAIGN_DESTINATION/workflow.yaml
```

Até aqui nenhum experimento científico deve ter sido submetido.

## 8. Execute

```bash
monan-jedi-workflow campaign run my-experiment/campaign.yaml
```

Acompanhe:

```bash
monan-jedi-workflow campaign status my-experiment/campaign.yaml
```

## 9. Valide três dias

Antes de ampliar o período, confirme:

- todos os ciclos terminaram;
- observações foram convertidas e usadas;
- JEDI terminou com seus marcadores de sucesso;
- análises foram produzidas;
- forecasts MPAS terminaram;
- cada forecast forneceu o estado esperado ao ciclo seguinte;
- horários NetCDF são coerentes;
- logs não mostram erro científico silencioso.

## 10. Amplie sem mudar a ciência

Crie uma nova campanha/destination e altere apenas a duração:

```text
P3D -> P7D -> P30D -> P365D
```

Se for necessário alterar Python apenas porque a duração aumentou, isso deve
ser tratado como defeito do workflow, não como procedimento do usuário.

## Próximo marco

O template `examples/case` será fechado com o baseline científico 2025 antes
de ser declarado pronto para produção. Até lá, nenhum valor científico de
exemplo deve ser interpretado como recomendação universal.


## O que NÃO usar

Não há um segundo diretório de exemplos para escolher. O caminho mantido é
`examples/case/`. Material de reprodução histórica foi retirado da árvore
ativa e permanece preservado em `archive/pre-cleanup-2026-10-01`.

Os comandos de stage (`jedi-prepare`, `mpas-prepare`, `obs2ioda-run` etc.)
são usados pelo workflow e servem para diagnóstico/desenvolvimento. Para uma
campanha normal, use a interface `campaign`.
