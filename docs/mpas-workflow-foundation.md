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
                    └── exportação B-matrix       └── PBS (adaptador)
```

Responsabilidades:

- `input_sources.py`: resolve fontes locais, de infraestrutura, GFS, reanálises ou HTTP; valida cobertura temporal declarada, malha, tamanho, extensão e checksum; baixa somente por comando explícito.
- `workflow_plan.py`: valida `workflow.yaml`, seleciona UNGRIB de maneira explícita, constrói o grafo de dependências, grava plano/versionamento e exporta o contrato de entrada da matriz B.
- estágios existentes (`wps_stage.py`, `init_stage.py`, `mpas_stage.py`, `obs2ioda_stage.py`): renderizam, executam e validam apenas sua responsabilidade.
- adaptadores PBS: continuam sendo a única parte dependente do escalonador.

## Modos

| Modo | Objetivo | Estágios padrão |
|---|---|---|
| `prepare` | Preparar entradas e condição inicial | input, WPS opcional, MPAS init |
| `forecast` | Produzir uma previsão MPAS | input, WPS opcional, init, forecast |
| `cycle` | Fundo MPAS + análise MPAS-JEDI | input, WPS opcional, init, forecast, JEDI |
| `bmatrix` | Preparar amostras e a entrega ao pipeline externo | input, WPS opcional, init, forecast, contrato B |

## Fontes de dados

`inputs.yaml` usa um adaptador por fonte. A escolha é somente declarativa:

- `local`: arquivo já presente no experimento ou em um caminho montado;
- `infrastructure`: produto fixo mantido pela infraestrutura (malha, invariantes, tabelas ou arquivos estáticos); nunca tenta baixar;
- `gfs`, `reanalysis` e `http`: URL configurada e destino local. A transferência ocorre somente com `input-fetch` ou `workflow-run --execute --fetch-inputs`.

O adaptador não tenta inferir conteúdo de GRIB/NetCDF sem bibliotecas de domínio. Em vez disso, valida o contrato fornecido: arquivo, tamanho mínimo, extensão, checksum opcional, período coberto e identificador de malha. A validação científica profunda do estado é responsabilidade de MPAS, WPS e MPAS-JEDI.

## Regra para UNGRIB

`workflow.use_wps` tem três valores:

- `auto`: ativa WPS/UNGRIB apenas para `grib`, `grib1`, `grib2`, `grb` ou `grb2`;
- `always`: força WPS para uma fonte cujo pré-processamento externo é parte do caso;
- `never`: exige que o produto de entrada já seja utilizável pelo estágio seguinte.

Isto permite um primeiro ciclo com GRIB/GFS e ciclos subsequentes alimentados por estados MPAS, assim como a geração de B a partir de amostras já disponíveis, sem criar fluxos duplicados.

## CLI

```bash
# Não executa nada: valida configurações, decide WPS e mostra o grafo
monan-jedi-workflow workflow-plan experiments/case \
  --cycle 2018-04-15T00:00:00Z

# Valida o produto de uma fonte individual e registra a proveniência
monan-jedi-workflow input-validate experiments/case \
  --source local_mpas_init --cycle 2018-04-15T00:00:00Z --checksum

# Dry-run é o comportamento padrão
monan-jedi-workflow workflow-run experiments/case \
  --cycle 2018-04-15T00:00:00Z

# Executa apenas a próxima fronteira segura; PBS requer --submit
monan-jedi-workflow workflow-run experiments/case \
  --cycle 2018-04-15T00:00:00Z --execute --submit

# Para mode: bmatrix, exporta somente a proveniência das amostras para o outro repo
monan-jedi-workflow prepare-bmatrix experiments/bmatrix \
  --cycle 2018-04-15T00:00:00Z --checksum
```

Cada execução grava `.monan-jedi-workflow/<cycle>/workflow-plan.json` e um relatório por fonte. O mesmo plano é reutilizado se o *fingerprint* de configuração for igual. Caso o YAML mude, o usuário precisa empregar `workflow-plan --force`, evitando uma retomada silenciosa com semântica diferente.

## Integração com a matriz B

O modo `bmatrix` não modifica e não chama `mpas-bmatrix-global`. Ele exporta um JSON portável contendo malha, ciclo, fonte de dados, checksums opcionais e a lista de arquivos de amostras. O consumidor planejado é o branch `refactor/bflow-python-pipeline`, que recebe amostras e executa separadamente VBAL → HDIAG → NICAS → DIRAC → SO. Dessa forma, o produtor de estados MPAS e a calibração SABER/BUMP permanecem desacoplados.

## Limitações conhecidas

- URLs oficiais e credenciais de GFS/reanálises não são codificadas no pacote; ficam no arquivo local do experimento para evitar acoplamento a um provedor.
- O adaptador de fonte não faz inspeção semântica de variáveis NetCDF/GRIB. Essa validação requer ferramentas específicas do ambiente e pertence a uma etapa opcional de inspeção futura.
- O comportamento de PBS, módulos e caminhos absolutos permanece específico do site e continua configurado nos adaptadores existentes para JACI.
- Uma submissão não é considerada sucesso científico: a retomada valida produtos e marcadores de log antes de avançar.
