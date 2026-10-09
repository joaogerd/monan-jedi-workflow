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

Depois verifique as variáveis do ambiente:

```bash
printf 'CONDA_PREFIX=%s\n' "$CONDA_PREFIX"
printf 'PYTHONPATH=%s\n' "${PYTHONPATH:-<not set>}"
```

Uma saída correta será semelhante a esta:

```text
/home2/<usuario>/.conda/envs/monan-jedi/bin/python

3.11.x (...) [...]
/home2/<usuario>/.conda/envs/monan-jedi/bin/python
/home2/<usuario>/.conda/envs/monan-jedi/lib/python3.11/site-packages/numpy/__init__.py

CONDA_PREFIX=/home2/<usuario>/.conda/envs/monan-jedi
PYTHONPATH=<not set>
```

Os números exatos da versão e o nome do usuário podem ser diferentes. O
importante é entender **de onde cada componente está sendo carregado**.

> [!NOTE]
> #### Como saber se o Checkpoint 1 está correto
>
> Confira cada item:
>
> - **[OK] Python selecionado:** a saída de `command -v python` termina em
>   `.conda/envs/monan-jedi/bin/python`. Isso confirma que o comando `python`
>   pertence ao ambiente Conda criado para o MONAN-JEDI.
> - **[OK] Versão do Python:** a primeira linha produzida pelo comando Python
>   começa com `3.11`. Valores como `3.11.10` ou `3.11.16` são versões
>   diferentes da mesma série Python 3.11 e estão corretos para este tutorial.
> - **[OK] Executável Python:** `sys.executable` também termina em
>   `.conda/envs/monan-jedi/bin/python`. Isso confirma que o Python realmente
>   executado é o mesmo que o shell encontrou.
> - **[OK] NumPy:** `numpy.__file__` está abaixo de
>   `.conda/envs/monan-jedi/lib/python3.11/site-packages/`. Isso confirma que o
>   NumPy pertence ao mesmo ambiente Conda.
> - **[OK] Ambiente Conda:** `CONDA_PREFIX` termina em
>   `.conda/envs/monan-jedi`. Essa variável identifica o ambiente atualmente
>   ativo.
> - **[OK] PYTHONPATH:** deve aparecer como `PYTHONPATH=<not set>`. Assim, um
>   caminho externo não está forçando o Python a importar pacotes de outra
>   instalação.
>
> Um sinal claro de problema seria, por exemplo, o Python vindo de
> `monan-jedi`, mas o NumPy vindo de um caminho contendo
> `spack-stack/.../site-packages`. Isso significaria que dois ambientes Python
> foram misturados.
>
> **Se todos os seis itens acima estiverem OK, o Checkpoint 1 foi concluído e
> você pode prosseguir para a seção 2.3. Se algum item for diferente, não
> prossiga: primeiro identifique por que o ambiente não corresponde ao esperado.**
>
O spack-stack científico será carregado somente depois que este checkpoint
estiver correto.

### 2.3 Prepare o runtime científico MONAN-JEDI

Antes de instalar os comandos que executarão a campanha, confirme que existe
uma instalação válida do **MONAN-JEDI**. Ele fornece os executáveis científicos
(MONAN/MPAS, JEDI, Obs2IODA e WPS) usados pelo restante do tutorial.

No JACI, o caminho padrão da instalação é:

```text
/p/projetos/monan_das/<usuario>/build/monan-jedi
```

#### Verifique se o MONAN-JEDI já está instalado

Execute:

```bash
test -f /p/projetos/monan_das/$USER/build/monan-jedi/share/monan-jedi/install-manifest.json \
  && echo "[OK] MONAN-JEDI instalado" \
  || echo "[FALHA] MONAN-JEDI ainda não está instalado"
```

Se aparecer `[OK]`, **não reinstale** o MONAN-JEDI. Vá diretamente para
**Obtenha o ambiente publicado pelo MONAN-JEDI**, abaixo.

Se aparecer `[FALHA]`, faça a instalação antes de continuar.

#### Se necessário, instale o MONAN-JEDI

Mantenha o código-fonte na área de projetos:

```bash
mkdir -p /p/projetos/monan_das/$USER/projects
cd /p/projetos/monan_das/$USER/projects

git clone https://github.com/GAD-DIMNT-CPTEC/MONAN-JEDI.git
cd MONAN-JEDI
```

Valide primeiro a configuração JACI:

```bash
python3 scripts/lib/read_config.py --check config/jaci.yaml
python3 scripts/check_config_documentation.py
```

Verifique então se o spack-stack configurado pelo MONAN-JEDI pode ser ativado:

```bash
bash scripts/monan-jedi.sh load --config config/jaci.yaml
```

Se os comandos anteriores terminarem sem erro, execute a instalação completa:

```bash
bash scripts/monan-jedi.sh all --config config/jaci.yaml
```

No JACI, usando a configuração padrão, o runtime resultante será publicado em:

```text
/p/projetos/monan_das/<usuario>/build/monan-jedi
```

#### Obtenha o ambiente publicado pelo MONAN-JEDI

Independentemente de a instalação já existir ou ter sido criada agora, use o
próprio MONAN-JEDI para informar ao shell onde estão o runtime e o spack-stack
correspondente:

```bash
cd /p/projetos/monan_das/$USER/projects/MONAN-JEDI

eval "$(bash scripts/monan-jedi.sh env --config config/jaci.yaml)"
```

Não digite manualmente os caminhos de `MONAN_JEDI_INSTALL_ROOT` e
`STACK_ROOT`. O comando acima obtém os dois valores da mesma configuração
usada pelo MONAN-JEDI, evitando combinar um runtime com um spack-stack
diferente.

### Checkpoint 2 — runtime MONAN-JEDI

Execute:

```bash
printf 'MONAN_JEDI_INSTALL_ROOT=%s\n' "$MONAN_JEDI_INSTALL_ROOT"
printf 'STACK_ROOT=%s\n' "$STACK_ROOT"

test -f "$MONAN_JEDI_INSTALL_ROOT/share/monan-jedi/install-manifest.json" \
  && echo "[OK] manifesto do runtime encontrado" \
  || echo "[FALHA] manifesto do runtime não encontrado"
```

Para a instalação JACI padrão, a primeira linha será semelhante a:

```text
MONAN_JEDI_INSTALL_ROOT=/p/projetos/monan_das/<usuario>/build/monan-jedi
STACK_ROOT=<spack-stack selecionado pela configuração MONAN-JEDI>
[OK] manifesto do runtime encontrado
```

> [!NOTE]
> #### Como saber se o Checkpoint 2 está correto
>
> Confira cada item:
>
> - **[OK] Runtime:** `MONAN_JEDI_INSTALL_ROOT` está preenchido e, na
>   instalação padrão do JACI, aponta para
>   `/p/projetos/monan_das/<usuario>/build/monan-jedi`.
> - **[OK] spack-stack:** `STACK_ROOT` está preenchido. Você não precisa
>   descobrir ou escolher esse caminho manualmente neste tutorial; ele vem da
>   configuração do MONAN-JEDI.
> - **[OK] Manifesto:** o último comando imprime
>   `[OK] manifesto do runtime encontrado`.
>
> O MONAN-JEDI publica o runtime científico e informa ao restante do ecossistema
> quais são suas duas âncoras públicas: `MONAN_JEDI_INSTALL_ROOT` e
> `STACK_ROOT`.
>
> **Se os três itens estiverem OK, o runtime científico está pronto e você pode
> prosseguir para a seção 2.4. Se algum item falhar, não prossiga.**

### 2.4 Instale os comandos Python

Agora que o runtime científico foi validado, instale o **simpleWorkflow** e o
**monan-jedi-workflow** no ambiente Conda `monan-jedi`.

Os códigos-fonte ficam fora do ambiente Conda. Use a área de projetos:

```bash
mkdir -p /p/projetos/monan_das/$USER/projects
cd /p/projetos/monan_das/$USER/projects
```

A organização esperada será:

```text
/p/projetos/monan_das/<usuario>/projects/
├── MONAN-JEDI/              <- instalação e publicação do runtime científico
├── simpleWorkflow/          <- código-fonte do orquestrador
└── monan-jedi-workflow/     <- código-fonte da campanha

$HOME/.conda/envs/monan-jedi/
└── ...                      <- ambiente Python que executa os dois comandos
```

Os repositórios não são clonados dentro do ambiente Conda.
`python -m pip install -e .` registra cada checkout no ambiente Python ativo.

#### Instale o simpleWorkflow

```bash
cd /p/projetos/monan_das/$USER/projects

git clone https://github.com/joaogerd/simpleWorkflow.git
cd simpleWorkflow
python -m pip install -e .
```

Se o diretório `simpleWorkflow` já existir, não o clone novamente:

```bash
cd /p/projetos/monan_das/$USER/projects/simpleWorkflow
python -m pip install -e .
```

#### Instale o monan-jedi-workflow

```bash
cd /p/projetos/monan_das/$USER/projects

git clone --branch feature/2025-reference-case https://github.com/joaogerd/monan-jedi-workflow.git
cd monan-jedi-workflow
python -m pip install -e .
```

Se o repositório já existir, confira `git status`, selecione a branch
`feature/2025-reference-case` e atualize-a com `git pull --ff-only` antes de
executar `python -m pip install -e .`. Preserve alterações locais; não use reset/clean.

### Checkpoint 3 — comandos do workflow

Execute:

```bash
command -v swf
command -v monan-jedi-workflow

swf --help
monan-jedi-workflow --help
```

Uma saída correta para os dois primeiros comandos será semelhante a:

```text
/home2/<usuario>/.conda/envs/monan-jedi/bin/swf
/home2/<usuario>/.conda/envs/monan-jedi/bin/monan-jedi-workflow
```

> [!NOTE]
> #### Como saber se o Checkpoint 3 está correto
>
> Confira cada item:
>
> - **[OK] simpleWorkflow:** `command -v swf` termina em
>   `.conda/envs/monan-jedi/bin/swf`.
> - **[OK] monan-jedi-workflow:** `command -v monan-jedi-workflow` termina em
>   `.conda/envs/monan-jedi/bin/monan-jedi-workflow`.
> - **[OK] interface do simpleWorkflow:** `swf --help` mostra a ajuda do
>   comando sem erro de importação.
> - **[OK] interface da campanha:** `monan-jedi-workflow --help` mostra a
>   ajuda do comando sem erro de importação.
> - **[OK] checkouts:** os diretórios
>   `/p/projetos/monan_das/$USER/projects/simpleWorkflow` e
>   `/p/projetos/monan_das/$USER/projects/monan-jedi-workflow` existem.
>
> **Se todos os itens estiverem OK, a preparação dos comandos está concluída e
> você pode prosseguir para a próxima seção. Se algum item for diferente, não
> prossiga.**

## 3. Caso de referência 2025 fornecido pelo repositório

O `examples/case/` não é mais um esqueleto abstrato. Ele representa o primeiro
caso de referência a validar no JACI:

```text
primeira análise : 2025-09-01 00Z
fim P7D          : 2025-09-08 00Z
cadência         : 6 h
malha            : x1.10242 (~240 km)
níveis           : 55
MPAS             : 128 MPI ranks
FGAT states      : 3 h
JEDI             : 3D-FGAT
observações      : GDAS PREPBUFR — radiossondas + superfície; GNSS-RO
```

A configuração científica do JEDI vem do experimento [M3 de três dias](https://github.com/GAD-DIMNT-CPTEC/monan-jedi-2026/blob/5aeed60857447bf229416327441589ca52e29e39/docs/relatorios/M3_3dias.md).
Mantemos SABER/BUMP (NICAS, StdDev e balanço vertical), os três observers,
os filtros QC e DRPCG com 10 iterações. As datas e os dados dinâmicos de
2018 não são reutilizados. A execução de 2025 ainda precisa ser validada na JACI.

### 3.1 Caminhos padrão da JACI

Não é necessário exportar DATA_ROOT, MESH_ROOT, BMATRIX_ROOT, GFS_ROOT ou
WORKFLOW_ROOT. Os YAMLs do caso já declaram os caminhos padrão abaixo.
`USER` é a variável da própria sessão de login. Mantenha o ambiente
MONAN-JEDI carregado conforme a seção 2 (runtime e stack continuam necessários).

| Conteúdo | Caminho padrão |
|---|---|
| Observações baixadas | `/p/projetos/monan_das/$USER/external-inputs/observations` |
| Malha | `/p/projetos/monan_das/share/MONAN-JEDI-Data/meshes/quasi_uniform/x1.10242_240km` |
| GFS inicial | `/p/projetos/monan_das/$USER/data/gfs` |
| Checkout do workflow | `/p/projetos/monan_das/$USER/projects/monan-jedi-workflow` |

Se seu checkout ou armazenamento pessoal estiver em outro lugar, ajuste
`variables.workflow_root`, `variables.data_root` e `variables.gfs_root`
nos YAMLs correspondentes do caso copiado. Isso é configuração persistente;
não precisa repetir exports em cada login.

A B compartilhada já foi copiada para
`/p/projetos/monan_das/share/MONAN-JEDI-Data/covariance/x1.10242_240km/55levels/`.
O `jedi.yaml` usa esse caminho diretamente: **não é necessário exportar
MONAN_JEDI_BMATRIX_ROOT**. Em outro site, ajuste `jedi.variables.bmatrix_root`.
O diretório contém `NICAS/`, `HDIAG/mpas.stddev.nc` e `VBAL/` e é ligado
como `Data/covariance` no diretório JEDI de cada ciclo.
A configuração usa SABER/BUMP. A cópia ainda precisa ter origem e hashes
registrados; a compatibilidade científica de 2025 será verificada na execução.

O `MONAN-JEDI-Data` versiona o catálogo e os hashes. Os arquivos científicos
completos ficam na área compartilhada da JACI; clonar o GitHub não os baixa.
Use a coleção já importada, sem repetir a importação nem instalar LFS.

| Componente | Local consumido pelo caso |
|---|---|
| Grid | `/p/projetos/monan_das/share/MONAN-JEDI-Data/meshes/quasi_uniform/x1.10242_240km/mesh/x1.10242.grid.nc` |
| Grafo | `/p/projetos/monan_das/share/MONAN-JEDI-Data/meshes/quasi_uniform/x1.10242_240km/graph/x1.10242.graph.info` |
| Invariant | `/p/projetos/monan_das/share/MONAN-JEDI-Data/meshes/quasi_uniform/x1.10242_240km/static/x1.10242.invariant.nc` |
| Partitions | `/p/projetos/monan_das/share/MONAN-JEDI-Data/meshes/quasi_uniform/x1.10242_240km/partitions/x1.10242.graph.info.part.N` |
| Tabelas de física | `/p/projetos/monan_das/share/MONAN-JEDI-Data/physics/mpas/files` |
| Matriz B | `/p/projetos/monan_das/share/MONAN-JEDI-Data/covariance/x1.10242_240km/55levels` |

O MONAN-JEDI-Data reúne agora malhas e tabelas de física. B, GFS e
observações continuam sendo conjuntos separados.
Os hashes verificam a identidade dos arquivos; não demonstram por si só
compatibilidade científica do invariant com o caso de 55 níveis.


### 3.2 Tabelas de física compartilhadas

Os YAMLs do forecast cíclico e de inicialização já apontam `physics_root`
para `/p/projetos/monan_das/share/MONAN-JEDI-Data/physics/mpas/files`.
Não é necessário exportar outra variável nem copiar tabelas para cada usuário.
Em outro site, ajuste `physics_root` nos dois YAMLs.

O conjunto contém 13 arquivos: `CAM_ABS_DATA.DBL`, `CAM_AEROPT_DATA.DBL`,
`GENPARM.TBL`, `LANDUSE.TBL`, `OZONE_DAT.TBL`, `OZONE_LAT.TBL`,
`OZONE_PLEV.TBL`, `RRTMG_LW_DATA`, `RRTMG_LW_DATA.DBL`,
`RRTMG_SW_DATA`, `RRTMG_SW_DATA.DBL`, `SOILPARM.TBL` e `VEGPARM.TBL`.
São dados de radiação, ozônio e parametrizações de superfície.
Namelists/streams ficam nos templates do caso; invariant e partitions ficam
na coleção da malha.

**Como obter:** na JACI, reutilize a cópia compartilhada já cadastrada.
O GitHub publica o manifesto e a documentação, não os arquivos completos.
Se a coleção local estiver ausente, recupere uma cópia do conjunto indicado
em `provenance.source_directory` do manifesto, ou solicite a coleção ao
responsável pelo armazenamento compartilhado. O nome do diretório antigo
é informação de origem, não um caminho exigido pelo workflow.
Ainda não existe um downloader automático publicado para este conjunto.
Não substitua silenciosamente por tabelas de outra versão.

**Checkpoint — integridade das tabelas**

Execute no ambiente Python preparado na seção 2:

```bash
python - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path("/p/projetos/monan_das/share/MONAN-JEDI-Data/physics/mpas")
manifest = json.loads((root / "manifest.yaml").read_text())
failures = []
for item in manifest["files"]:
    path = root / item["path"]
    if not path.is_file():
        failures.append(f"Ausente: {path}")
        continue
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    if path.stat().st_size != item["size_bytes"] or digest.hexdigest() != item["sha256"]:
        failures.append(f"Conteúdo divergente: {path}")
    else:
        print(f"[OK] {path.name}")
if failures:
    raise SystemExit("\\n".join(failures))
print(f"Integridade OK: {len(manifest['files'])} tabelas.")
PY
```

O resultado esperado é 13 linhas `[OK]` e `Integridade OK: 13 tabelas.`
O manifesto preserva a origem no tutorial de setembro de 2025 e registra
compatibilidade científica como ainda não validada. SHA-256 verifica a cópia;
a execução com o runtime selecionado continua exigindo validação.

### 3.3 Dados necessários para iniciar P7D

A inicialização da primeira análise começa seis horas antes, em
**2025-08-31 18Z**. O caso espera o GFS f000 em:

```text
/p/projetos/monan_das/$USER/data/gfs/2025083118/gfs.t18z.pgrb2.0p25.f000
```

E espera PREPBUFR para cada análise de 2025-09-01 00Z até
2025-09-08 00Z:

```text
/p/projetos/monan_das/$USER/external-inputs/observations/prepbufr/2025/
  prepbufr.gdas.20250901.t00z.nr.48h
  prepbufr.gdas.20250901.t06z.nr.48h
  ...
  prepbufr.gdas.20250908.t00z.nr.48h
```

O PREPBUFR é o produto GDAS/NCEP da coleção NSF NCAR GDEX d337000. O caso não
silencia arquivos ausentes: `campaign check` lista os ciclos que ainda
precisam ser staged.

### 3.4 Aquisição dos dados dinâmicos

Depois de copiar o caso (seção 4), execute na raiz dele:

```bash
monan-jedi-workflow campaign fetch campaign.yaml
```

O comando mostra `[CYCLE n/29]`, arquivo, URL e destino antes da transferência.
A cada cinco segundos, `[PROGRESS]` informa MiB recebidos ou espera pelo servidor;
`[DONE]` indica a conclusão, `[EXTRACT]` a extração do GPSRO e `[RETRY]` uma
nova tentativa de transporte. Se interromper com Ctrl+C, execute novamente:
entradas já concluídas são reutilizadas; transferências incompletas são refeitas.

O comando adquire PREPBUFR e GPSRO para as 29 análises. GPSRO usa o arquivo
diário da coleção GDEX d735000 e extrai o BUFR da hora requerida. As entradas
ficam em `external-inputs/observations/{prepbufr,gpsro}/2025/` do usuário.
A aquisição não reutiliza observações de 2018 e não baixa a B ou as tabelas.

O GFS inicial é um arquivo separado, necessário apenas para inicialização.
Use uma cópia já disponível ou baixe o f000 de 2025-08-31 18Z do bucket NOAA:

```bash
(
  set -e
  destino=/p/projetos/monan_das/$USER/data/gfs/2025083118
  arquivo="$destino/gfs.t18z.pgrb2.0p25.f000"
  mkdir -p "$destino"
  if [ ! -s "$arquivo" ]; then
    curl --fail --location --retry 3 \
      --output "$arquivo.part" \
      https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20250831/18/atmos/gfs.t18z.pgrb2.0p25.f000
    test -s "$arquivo.part"
    mv "$arquivo.part" "$arquivo"
  fi
)
```

Este download não inicia jobs. Se ele falhar, não prossiga com arquivo parcial.
O nome do arquivo deve permanecer como declarado em `initialization/wps.yaml`.

### Arquivo PREP48H ausente no catálogo

A coleção PREP48H de 2025 não lista o ciclo 2025-09-01 18Z:
https://gdex.ucar.edu/datasets/d337000/filelist/32025/
O servidor retorna HTTP 404; não é erro de certificado.
A coleção PREPNR lista o mesmo ciclo e todos os 29 ciclos de P7D:
https://gdex.ucar.edu/datasets/d337000/filelist/42025/

PREPNR exclui ACARS/AMDAR; PREP48H os inclui. Este caso assimila somente
radiossondas e superfície do PREPBUFR, além de GPSRO separado. Uma alternativa
é selecionar PREPNR para **toda a campanha**, conservando datas, operators e QC.
Os produtos não são declarados equivalentes byte a byte; registre a coleção
selecionada e confira contagens/QC após conversão. Não misture silenciosamente
as coleções nem renomeie PREPNR como PREP48H.

Para selecionar PREPNR no caso copiado, ajuste somente estas duas entradas:

```yaml
# obs2ioda.yaml -> obs2ioda.variables.prepbufr_input
prepbufr_input: "{data_root}/observations/prepnr/{cycle_year}/prepbufr.gdas.{cycle_yyyymmddhh}.nr"

# profile.yaml -> profile.observation_acquisition.providers.prepbufr-conventional.url
url: "https://data.gdex.ucar.edu/d337000/prepnr/{cycle_year}/prepbufr.gdas.{cycle_year}{cycle_month}{cycle_day}{cycle_hour}.nr"
```

Execute novamente `campaign fetch`. Arquivos PREP48H já baixados permanecem
guardados e não são consumidos por esse caminho PREPNR. A disponibilidade
do catálogo confirma a entrada; o acesso HTTPS deve ser validado na JACI.

### Checkpoint — assets fixos

```bash
test -s "/p/projetos/monan_das/share/MONAN-JEDI-Data/meshes/quasi_uniform/x1.10242_240km/static/x1.10242.invariant.nc"
test -s "/p/projetos/monan_das/share/MONAN-JEDI-Data/meshes/quasi_uniform/x1.10242_240km/mesh/x1.10242.grid.nc"
test -s "/p/projetos/monan_das/share/MONAN-JEDI-Data/meshes/quasi_uniform/x1.10242_240km/graph/x1.10242.graph.info"
test -s "/p/projetos/monan_das/share/MONAN-JEDI-Data/meshes/quasi_uniform/x1.10242_240km/partitions/x1.10242.graph.info.part.64"
test -s "/p/projetos/monan_das/share/MONAN-JEDI-Data/meshes/quasi_uniform/x1.10242_240km/partitions/x1.10242.graph.info.part.128"
test -s "/p/projetos/monan_das/$USER/data/gfs/2025083118/gfs.t18z.pgrb2.0p25.f000"
test -d "/p/projetos/monan_das/share/MONAN-JEDI-Data/covariance/x1.10242_240km/55levels"
```

Todos devem terminar com status zero antes de iniciar a campanha.

## 4. Crie seu caso a partir do único template

Volte à raiz do checkout do `monan-jedi-workflow`. Copie o diretório inteiro:

```bash
cd "/p/projetos/monan_das/$USER/projects/monan-jedi-workflow"
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
    wps.yaml
    mpas_init.yaml
    mpas.yaml
  templates/
    README.md
```

O diretório inclui também `initialization/templates/` e os templates científicos
referenciados pelos YAMLs. Preserve-os na cópia; a lista acima resume o layout.

O `workflow.yaml` **não existe ainda e não deve ser escrito pelo usuário**.
Ele será produzido por `campaign create` depois que a configuração passar no
preflight.

### Checkpoint 4 — caso criado

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
  name: meu-experimento-7d
  start: 2025-09-01T00:00:00Z
  duration: P7D
  cycle_interval_hours: 6
  destination: cases/meu-experimento-7d
```

Você precisa decidir somente o nome, a primeira análise, a duração e a cadência.
A data só pode ser escolhida depois de confirmar que inicialização e observações
existem para todo o período.

Valide esta rodada de sete dias antes de ampliar para P30D.

Referência completa: [configuração da campanha](configuration/campaign.md).

### Checkpoint 5 — período

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

O caso fornece `observation_acquisition.enabled: true` e providers PREPBUFR
e GPSRO do experimento M3. `campaign fetch campaign.yaml` reutiliza entradas
locais e baixa as ausentes. `campaign create` e `campaign run` também fazem
essa aquisição. Os 29 ciclos incluem a primeira análise. O download precisa
ser conferido na JACI; erros de acesso ou arquivos ausentes interrompem a preparação.

### Checkpoint 6 — ligação do caso

```bash
test -f jedi.yaml
test -f mpas.yaml
test -f initialization/wps.yaml
test -f initialization/mpas_init.yaml
test -f initialization/mpas.yaml
test -f obs2ioda.yaml
```

Os seis comandos devem terminar sem mensagem de erro.

### 5.3 `mpas.yaml` — forecast cíclico MONAN/MPAS

Abra:

```bash
vi mpas.yaml
```

Preencha, no mínimo:

1. `static_root`: invariant em `{mesh_root}/static`; partição em
   `{mesh_root}/partitions`; tabelas de física em `physics_root`;
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

### Checkpoint 7 — MPAS

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

### Checkpoint 8 — observações

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

### Checkpoint 9 — JEDI

```bash
grep -n 'EDITAR' jedi.yaml
```

Esse comando também deve terminar sem retornar linhas.

### 5.6 `initialization/` — construa o primeiro background

A primeira análise é 2025-09-01 00Z. A inicialização começa no ciclo anterior,
2025-08-31 18Z, e é inteiramente reproduzível pela campanha:

```text
GFS f000
  -> initialization/wps.yaml
  -> WPS/ungrib
  -> initialization/mpas_init.yaml
  -> mpas_init_atmosphere
  -> initialization/mpas.yaml
  -> MONAN/MPAS 18Z -> 00Z
  -> primeiro background JEDI
```

Os três arquivos têm responsabilidades distintas:

- `wps.yaml`: decodifica o GFS;
- `mpas_init.yaml`: interpola o GFS para a malha x1.10242;
- `mpas.yaml`: integra MONAN/MPAS por 6 h e produz os estados +3 h/+6 h.

### Checkpoint 10 — inicialização

```bash
grep -RIn 'EDITAR' initialization
test -f initialization/wps.yaml
test -f initialization/mpas_init.yaml
test -f initialization/mpas.yaml
```

O `grep` não deve retornar placeholders e os três `test` devem terminar com
status zero.

### 5.7 `templates/` — arquivos científicos consumidos pelos executáveis

Leia primeiro:

```bash
cat templates/README.md
```

O caso real precisa fornecer os namelists, streams e `variational.yaml`
referenciados pelos YAMLs anteriores. Não use um template de outra malha ou
experimento sem verificar geometry, níveis, datas, B, observers e outputs.

### Checkpoint 11 — nenhum placeholder restante

Da raiz de `my-experiment`:

```bash
grep -RIn 'EDITAR' \
  campaign.yaml profile.yaml mpas.yaml obs2ioda.yaml jedi.yaml initialization templates
```

Para um caso pronto, o comando não deve retornar nenhuma configuração ativa
não resolvida.

## 6. Primeiro teste no JACI

A partir deste ponto, pare de editar o caso e teste exatamente o que será
executado. Faça os checkpoints abaixo no mesmo shell limpo preparado na seção 2.

### Checkpoint 12 — ambiente final

```bash
echo "CONDA_PREFIX=$CONDA_PREFIX"
echo "MONAN_JEDI_INSTALL_ROOT=$MONAN_JEDI_INSTALL_ROOT"
echo "STACK_ROOT=$STACK_ROOT"

command -v python
command -v swf
command -v monan-jedi-workflow
```

Não prossiga se alguma âncora estiver vazia ou se os comandos Python vierem de
ambientes diferentes.

### Checkpoint 13 — arquivos científicos mínimos

```bash
test -s "/p/projetos/monan_das/$USER/data/gfs/2025083118/gfs.t18z.pgrb2.0p25.f000"
test -s "/p/projetos/monan_das/share/MONAN-JEDI-Data/meshes/quasi_uniform/x1.10242_240km/static/x1.10242.invariant.nc"
test -s "/p/projetos/monan_das/share/MONAN-JEDI-Data/meshes/quasi_uniform/x1.10242_240km/partitions/x1.10242.graph.info.part.128"
test -d "/p/projetos/monan_das/share/MONAN-JEDI-Data/covariance/x1.10242_240km/55levels"

for hh in 00 06 12 18; do
  test -s "/p/projetos/monan_das/$USER/external-inputs/observations/prepbufr/2025/prepbufr.gdas.20250901.t${hh}z.nr.48h"
done
```

Esse laço é apenas uma checagem rápida do primeiro dia. O preflight seguinte
verifica automaticamente **todos os 29 ciclos** do P7D.

Antes do preflight, adquira as observações para todos os ciclos:

```bash
monan-jedi-workflow campaign fetch my-experiment/campaign.yaml
```

### Checkpoint 14 — preflight P7D

Da raiz do checkout:

```bash
monan-jedi-workflow campaign check my-experiment/campaign.yaml
```

O resultado deve terminar em:

```text
Preflight PASS
```

Se aparecer `FAIL`, **não use `campaign run`**. O erro do preflight passa a
ser o próximo problema a corrigir e deve ser resolvido antes de qualquer
submissão PBS.

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

## 9. Valide sete dias

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
P7D -> P30D
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
