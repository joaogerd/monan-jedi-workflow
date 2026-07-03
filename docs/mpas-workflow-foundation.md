# Fundação do workflow MPAS

## Propósito

Esta camada compõe os estágios já existentes de WPS/UNGRIB, `mpas_init_atmosphere`, `mpas_atmosphere` e MPAS-JEDI sem concentrar regras científicas, chamadas externas e submissão PBS no mesmo módulo. Ela foi construída para o baseline MPAS-JEDI `x1.10242` e preserva o uso de configurações fracionadas já adotado pelo repositório.

A referência científica do fluxo é: preparação de condição inicial, previsão de fundo, análise variacional e previsão em *warm start*. Para 3DVar-FGAT, a condição de fundo pode fornecer os estados no intervalo temporal enquanto a B e o incremento permanecem definidos no instante de análise. A camada de planejamento não altera os YAMLs de MPAS-JEDI: ela apenas declara dependências e a ordem de execução.

## Arquitetura

```text
inputs.yaml ──> input_sources.py ──> validação/proveniência
                    │
workflow.yaml ──> workflow_plan.py ──> plano idempotente ──> estado JSON
                    │                              │
                    ├── WPS/UNGRIB                ├── MPAS init
                    ├── MPAS forecast             ├── MPAS-JEDI
                    └── nmc_campaign.py           └── PBS (adaptador)
                               │
                               └── bflow-manifest.tsv ──> mpas-bmatrix-global
```

Responsabilidades:

- `input_sources.py`: resolve fontes locais, de infraestrutura, GFS, reanálises ou HTTP; valida cobertura temporal declarada, malha, tamanho, extensão e checksum; baixa somente por comando explícito.
- `workflow_plan.py`: valida `workflow.yaml`, seleciona UNGRIB de maneira explícita, constrói o grafo de dependências e grava plano/versionamento.
- `nmc_campaign.py`: calcula a geometria f024/f048, exige no mínimo quatro pares, valida `restart` e `mpasout` e exporta o manifesto BFLOW.
- `nmc_campaign_runner.py`: executa ou submete somente a próxima fronteira segura da campanha, retomando por produtos validados.
- estágios existentes (`wps_stage.py`, `init_stage.py`, `mpas_stage.py`, `obs2ioda_stage.py`): renderizam, executam e validam apenas sua responsabilidade.
- adaptadores PBS: continuam sendo a única parte dependente do escalonador.

## Modos

| Modo | Objetivo | Estágios padrão |
|---|---|---|
| `prepare` | Preparar entradas e condição inicial | input, WPS opcional, MPAS init |
| `forecast` | Produzir uma previsão MPAS | input, WPS opcional, init, forecast |
| `cycle` | Fundo MPAS + análise MPAS-JEDI | input, WPS opcional, init, forecast, JEDI |
| `bmatrix` | Produzir forecasts NMC e entregar pares ao BFLOW | input, WPS opcional, init, f024/f048, manifesto BFLOW |

## Fontes de dados

`inputs.yaml` usa um adaptador por fonte. A escolha é somente declarativa:

- `local`: arquivo já presente no experimento ou em um caminho montado;
- `infrastructure`: produto fixo mantido pela infraestrutura (malha, invariantes, tabelas ou arquivos estáticos); nunca tenta baixar;
- `gfs`, `reanalysis` e `http`: URL configurada e destino local. A transferência ocorre somente com `input-fetch`, `workflow-run --execute --fetch-inputs` ou `nmc-campaign-run --execute --fetch-inputs`.

O adaptador não tenta inferir conteúdo de GRIB/NetCDF sem bibliotecas de domínio. Em vez disso, valida o contrato fornecido: arquivo, tamanho mínimo, extensão, checksum opcional, período coberto e identificador de malha. A validação científica profunda do estado é responsabilidade de MPAS, WPS e MPAS-JEDI.

## Regra para UNGRIB

`workflow.use_wps` tem três valores:

- `auto`: ativa WPS/UNGRIB apenas para `grib`, `grib1`, `grib2`, `grb` ou `grb2`;
- `always`: força WPS para uma fonte cujo pré-processamento externo é parte do caso;
- `never`: exige que o produto de entrada já seja utilizável pelo estágio seguinte.

Isto permite um primeiro ciclo com GRIB/GFS e ciclos subsequentes alimentados por estados MPAS, sem criar fluxos duplicados.

## CLI

```bash
# Não executa nada: valida configurações, decide WPS e mostra o grafo
monan-jedi-workflow workflow-plan experiments/case \
  --cycle 2018-04-15T00:00:00Z

# Valida o produto de uma fonte individual e registra a proveniência
monan-jedi-workflow input-validate experiments/case \
  --source local_mpas_init --cycle 2018-04-15T00:00:00Z --checksum

# Dry-run é o comportamento padrão para uma campanha NMC
monan-jedi-workflow nmc-campaign-run experiments/bmatrix

# Executa a próxima fronteira; PBS continua exigindo --submit
monan-jedi-workflow nmc-campaign-run experiments/bmatrix --execute --submit

# Exporta o contrato consumido pelo BFLOW após validar restart e da_state
monan-jedi-workflow nmc-campaign-export-manifest experiments/bmatrix --checksum
```

Cada plano de campanha tem um *fingerprint*. Alterações de configuração exigem `nmc-campaign-plan --force`, evitando uma retomada silenciosa com semântica diferente.

## Integração com a matriz B

O modo `bmatrix` não chama VBAL, HDIAG, NICAS, DIRAC ou SO. Ele produz:

```text
bflow-manifest.tsv
bflow-manifest.json
```

O TSV contém `valid_time`, `f048` e `f024`, com caminhos para os arquivos `mpasout` do stream `da_state`. O consumidor é o branch `refactor/bflow-python-pipeline`:

```bash
mpasnmc validate-manifest --manifest bflow-manifest.tsv
mpasbflow all --manifest bflow-manifest.tsv --minimum-pairs 4 --clean-output
```

O produtor também exige `restart` para cada forecast como verificação estrutural. A B usa depois os `PTB_f48mf24.nc` criados pelo BFLOW, e não o restart nem o diagnóstico NMC direto.

## Limitações conhecidas

- URLs oficiais e credenciais de GFS/reanálises não são codificadas no pacote; ficam no arquivo local do experimento para evitar acoplamento a um provedor.
- O adaptador de fonte não faz inspeção semântica de variáveis NetCDF/GRIB. Essa validação requer ferramentas específicas do ambiente e pertence a uma etapa opcional de inspeção futura.
- O comportamento de PBS, módulos e caminhos absolutos permanece específico do site e continua configurado nos adaptadores existentes para JACI.
- Uma submissão não é considerada sucesso científico: a retomada valida produtos e marcadores de log antes de avançar.
- Uma campanha NMC exige `mpas.run_dir` contendo `{lead_hours}` para impedir colisão entre f024 e f048.
