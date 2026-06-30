# Arquitetura do workflow MPAS

## Objetivo

O workflow MPAS do `monan-jedi-workflow` organiza a preparação de entradas, geração de condições iniciais, forecast MPAS, observações IODA e futura assimilação MPAS-JEDI em etapas independentes e rastreáveis. A camada de orquestração é Python; PBS, WPS, MPAS e MPAS-JEDI permanecem executáveis externos chamados por adaptadores pequenos.

A cadeia científica é:

```text
fonte meteorológica
  -> validação/obtenção de entrada
  -> WPS/UNGRIB opcional
  -> mpas_init_atmosphere
  -> condição inicial MPAS
  -> mpas_atmosphere
  -> mpasout (da_state) / restart
  -> Obs2IODA
  -> MPAS-JEDI
```

Para matriz B, o workflow produz um contrato de amostras de forecast. A geração científica de VBAL, HDIAG, NICAS, SO e DIRAC continua no repositório especializado `mpas-bmatrix-global`.

## Separação de responsabilidades

| Componente | Responsabilidade |
| --- | --- |
| `mpas_pipeline.py` | Configuração de alto nível, fontes de dados, ativos estáticos, plano, estado e proveniência. |
| `wps_stage.py` | Staging, execução e validação de WPS/UNGRIB por ciclo. |
| `init_stage.py` | Staging, PBS, monitoramento e validação de `mpas_init_atmosphere`. |
| `mpas_stage.py` | Staging, PBS, monitoramento e validação do forecast `mpas_atmosphere`. |
| `obs2ioda_stage.py` | Conversão e validação de observações IODA. |
| `cli_mpas.py` | Interface de pesquisador: validar, planejar, preparar e publicar contrato de B. |
| `simpleWorkflow` | Orquestração genérica de ciclos e dependências; não contém regras MPAS/JEDI. |

## Configuração em duas camadas

A configuração de alto nível (`pipeline.yaml`) contém apenas decisões científicas e operacionais: ciclo, horas de forecast, fonte de dados, ativos estáticos, modo e número de processos. Arquivos de etapa (`wps.yaml`, `mpas_init.yaml`, `mpas.yaml`, `obs2ioda.yaml`) descrevem os adaptadores de execução e os templates de cada binário.

Essa divisão segue a decisão usada no branch `refactor/bflow-python-pipeline`: infraestrutura (caminhos, executáveis, malha, MPI e PBS) deve ficar separada das decisões científicas, e a configuração resolvida de cada workspace precisa ser preservada como evidência reprodutível.

## Fontes de dados

`pipeline.inputs.assets` aceita os provedores:

- `local`: arquivo já disponível no workspace do experimento;
- `infrastructure`: arquivo disponibilizado por uma infraestrutura local compartilhada;
- `gfs_http`: URL GFS declarada e cache local controlado;
- `reanalysis_http`: URL de reanálise declarada e cache local controlado;
- `http`: fonte remota genérica.

Entradas remotas não são baixadas durante `validate` ou `plan`. O download ocorre somente em `prepare --fetch`. O arquivo é gravado primeiro em `*.part` e só é publicado após possuir tamanho não nulo.

## Decisão de WPS

`pipeline.stages.wps` aceita `true`, `false` ou `auto`.

- `false`: a entrada já é adequada ao adaptador de inicialização;
- `true`: força WPS/UNGRIB;
- `auto`: usa WPS para fontes remotas configuradas como GRIB/reanálise e o pula para entradas locais já prontas.

A decisão é registrada no plano. Ela não deve ser inferida a partir da extensão do arquivo, pois um arquivo NetCDF local e um GRIB local podem exigir cadeias diferentes.

## Idempotência e estado

O workflow grava estado por ciclo em:

```text
<work_root>/.monan-jedi-mpas/state/<cycle_id>/<stage>.json
```

Cada registro contém a configuração serializada, fingerprints de entradas e saídas, ação realizada e data. Uma etapa é reutilizável apenas quando as saídas declaradas ainda existem, são arquivos e não estão vazias. `--force` invalida deliberadamente esse reaproveitamento.

Nenhuma etapa remove diretórios inteiros. Limpeza só ocorre para padrões declarados explicitamente pela etapa.

## Modos de operação

```text
prepare   valida/obtém dados, valida estáticos e monta estado
forecast  WPS opcional -> MPAS init -> MPAS forecast
cycle     forecast + Obs2IODA + fronteira para assimilação
bmatrix   forecast + contrato de amostras para o pipeline especializado
```

O modo `cycle` ainda não chama diretamente um JEDI cíclico: o baseline atual do JEDI não possui um adaptador de runtime por ciclo. O workflow para após validar backgrounds MPAS e observações IODA, onde uma integração cíclica de JEDI poderá ser conectada sem duplicar as etapas anteriores.

## Interface

Após instalar o pacote em modo desenvolvimento:

```bash
python -m pip install -e .

monan-jedi-mpas validate pipeline.yaml --cycle 2026-06-26T00:00:00Z
monan-jedi-mpas plan pipeline.yaml --cycle 2026-06-26T00:00:00Z
monan-jedi-mpas prepare pipeline.yaml --cycle 2026-06-26T00:00:00Z --dry-run
monan-jedi-mpas status pipeline.yaml --cycle 2026-06-26T00:00:00Z
monan-jedi-mpas prepare-bmatrix pipeline.yaml --cycle 2026-06-26T00:00:00Z
```

## Relação com o tutorial MPAS-JEDI

O tutorial distingue o primeiro background de cold start da previsão warm start após a análise. O primeiro usa condição inicial gerada a partir de GFS e campos invariantes; ciclos posteriores usam a análise como `mpasin`, preservando também o init para atualização de SST e gelo marinho. O forecast precisa disponibilizar o stream `da_state` como `mpasout.$Y-$M-$D_$h.$m.$s.nc` para o JEDI.

## Limites atuais

- A opção numérica de `WPS ./configure` depende do ambiente JACI e deve ser registrada no YAML do `MONAN-JEDI` antes de qualquer build real.
- Os templates físicos de `namelist.init_atmosphere`, `streams.init_atmosphere`, `namelist.atmosphere` e `streams.atmosphere` precisam ser extraídos e revisados da mesma revisão MPAS instalada.
- Não há ainda um adaptador Python de submissão/renderização do JEDI por ciclo; o código não deve usar o runtime estático atual em ciclos múltiplos.
- A geração B permanece no repositório especializado; o contrato publicado aqui evita acoplamento prematuro.
