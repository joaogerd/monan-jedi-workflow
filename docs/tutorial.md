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

## 3. Crie a configuração do experimento

Copie o template mantido:

```bash
cp -r examples/case my-experiment
cd my-experiment
```

Você encontrará um único conjunto de arquivos de usuário:

```text
my-experiment/
  campaign.yaml       quando e por quanto tempo executar
  profile.yaml        liga a campanha aos componentes abaixo
  jedi.yaml           análise/DA
  mpas.yaml           forecast MONAN/MPAS
  obs2ioda.yaml       observações
  initialization/     configuração do primeiro estado MPAS
  templates/          namelists, streams e YAML variacional (a preencher)
```

Não crie `workflow.yaml` manualmente. Ele é produto da materialização.

## 4. Configure na ordem correta

### 4.1 Campanha

Abra `campaign.yaml`. Para o primeiro teste escolha uma data para a qual todos
os dados estejam disponíveis e use:

```yaml
duration: P3D
```

Veja [campaign](configuration/campaign.md).

### 4.2 MONAN/MPAS

Abra `mpas.yaml` e confira malha, partição, forecast, intervalo dos estados
DA, namelist/streams e PBS.

Veja [MONAN/MPAS](configuration/mpas.md).

### 4.3 Observações

Abra `obs2ioda.yaml`. Para cada observação confirme origem, conversor e output
IODA. A lista `converters[*].outputs` é a lista de produtos que a campanha
espera.

Veja [observações](configuration/observations.md).

### 4.4 JEDI

Abra `jedi.yaml` e confira ciclo/janela, background, B, links das observações,
YAML variacional, recursos PBS e validação.

Depois confira o YAML variacional em `templates/`: geometry, variáveis,
B, observers, operadores, QC, erros e minimização.

Veja [JEDI](configuration/jedi.md).

## 5. Verifique antes de executar

Da raiz do repositório:

```bash
monan-jedi-workflow campaign check my-experiment/campaign.yaml
```

Corrija tudo que aparecer como erro. Não prossiga enquanto o preflight não
estiver limpo.

## 6. Materialize sem submeter

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

## 7. Execute

```bash
monan-jedi-workflow campaign run my-experiment/campaign.yaml
```

Acompanhe:

```bash
monan-jedi-workflow campaign status my-experiment/campaign.yaml
```

## 8. Valide três dias

Antes de ampliar o período, confirme:

- todos os ciclos terminaram;
- observações foram convertidas e usadas;
- JEDI terminou com seus marcadores de sucesso;
- análises foram produzidas;
- forecasts MPAS terminaram;
- cada forecast forneceu o estado esperado ao ciclo seguinte;
- horários NetCDF são coerentes;
- logs não mostram erro científico silencioso.

## 9. Amplie sem mudar a ciência

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
