# Modelo de configuração MPAS-JEDI para o MONAN-JEDI Workflow

## 1. Objetivo

Este documento registra o modelo conceitual e operacional de configuração de uma aplicação variacional MPAS-JEDI dentro do `monan-jedi-workflow`.

O objetivo não é substituir a documentação oficial do JEDI, mas consolidar, no próprio repositório, as regras técnicas que devem orientar a preparação, validação, renderização e execução controlada de experimentos MONAN-JEDI.

Este documento deve ser usado como referência para:

- organizar arquivos de configuração;
- renderizar o YAML final consumido pelo MPAS-JEDI;
- preparar o diretório de runtime;
- validar arquivos MPAS, JEDI, IODA e PBS;
- preservar o baseline funcional antes de generalizar o workflow;
- orientar futuras extensões para novos métodos, malhas, observações e ambientes HPC.

## 2. Papel do JEDI

O JEDI é a infraestrutura de assimilação de dados usada para executar aplicações como `mpasjedi_variational.x`.

No contexto deste workflow, o JEDI deve ser tratado como o sistema que consome um arquivo YAML completo, carrega os componentes necessários e executa a assimilação. O `monan-jedi-workflow` não implementa assimilação de dados. Ele prepara, valida e organiza os arquivos necessários para que o executável JEDI rode corretamente.

Uma execução típica possui a forma conceitual:

```bash
mpiexec -n <N> mpasjedi_variational.x variational.yaml
```

Em ambiente HPC, o launcher pode variar conforme o sistema:

```text
mpiexec
mpirun
srun
aprun
```

O workflow deve renderizar o script de submissão apropriado, mas não deve submeter jobs automaticamente.

## 3. Papel do OOPS

O OOPS é a camada genérica do JEDI que organiza a aplicação variacional. Ele define a função custo, a janela de assimilação, o background, as observações, a matriz de erro do background, o incremento, o minimizador e a análise final.

O YAML final de uma aplicação variacional precisa seguir a estrutura esperada pelo OOPS. Portanto, o workflow deve gerar esse YAML de forma determinística e validável.

## 4. Papel do MPAS-JEDI

O MPAS-JEDI é a interface entre o OOPS/JEDI e o modelo MPAS. Ele fornece classes específicas para:

- geometria MPAS;
- leitura e escrita de estados MPAS;
- incrementos;
- variáveis de análise;
- integração com `namelist.atmosphere`;
- integração com `streams.atmosphere`;
- uso de arquivos de malha e decomposição;
- uso de covariância estática ou baseada em SABER/BUMP.

A execução correta do MPAS-JEDI depende da consistência entre:

```text
YAML JEDI
namelist.atmosphere
streams.atmosphere
stream_list.atmosphere.*
arquivos NetCDF de background
arquivos estáticos da malha
arquivo de decomposição MPI
arquivos IODA de observação
arquivos de covariância de background
arquivos auxiliares e tabelas físicas do MPAS
```

Por isso, o workflow deve validar não apenas se os arquivos existem, mas se eles são coerentes entre si.

## 5. Estrutura geral de um YAML variacional

Um YAML variacional típico possui os seguintes blocos principais:

```yaml
cost function:
  cost type:
  time window:
  analysis variables:
  geometry:
  background:
  background error:
  observations:

variational:
  minimizer:
  iterations:

final:

output:
```

No `monan-jedi-workflow`, esse YAML final deve ser renderizado a partir de arquivos menores, organizados por responsabilidade:

```text
experiment.yaml      identidade, ciclo, método, geometria e paths principais
runtime.yaml         arquivos e diretórios necessários no runtime
variables.yaml       variáveis de análise, modelo e estado
observations.yaml    observadores, arquivos IODA, operadores e filtros
pbs.yaml             recursos e comandos de execução HPC
validation.yaml      contrato de validação do experimento
site.yaml            configuração do ambiente computacional/site
```

## 6. Bloco `cost function`

O bloco `cost function` define a função custo variacional. Ele contém o tipo de assimilação, a janela temporal, as variáveis de análise, a geometria, o background, a matriz de erro do background e as observações.

Exemplo conceitual:

```yaml
cost function:
  cost type: 3D-FGAT
  time window:
    begin: 2018-04-14T21:00:00Z
    length: PT6H
  analysis variables:
  - uReconstructZonal
  - uReconstructMeridional
  - temperature
  - spechum
  - surface_pressure
```

No workflow, esse bloco deve ser derivado principalmente de:

```text
experiment.yaml
variables.yaml
observations.yaml
```

## 7. Diferença entre 3DVar e 3D-FGAT

### 7.1 3DVar

No 3DVar clássico, o background, a matriz B e o incremento de análise são definidos em um único tempo. As observações são comparadas ao estado do modelo nesse tempo, ou em uma aproximação equivalente.

O 3DVar é conceitualmente mais simples e exige menos controle temporal dos arquivos de background.

### 7.2 3D-FGAT

O 3D-FGAT significa `First Guess at Appropriate Time`.

Nesse caso, as observações distribuídas ao longo da janela de assimilação são comparadas com o background no tempo apropriado. Isso exige maior cuidado com a janela temporal, os arquivos de background e a trajetória usada pela aplicação.

Mesmo no 3D-FGAT:

- o incremento continua definido em um único tempo;
- a matriz B continua associada a um tempo específico;
- o background precisa ser coerente com a janela de assimilação;
- as observações devem estar dentro da janela configurada.

O workflow deve validar explicitamente:

```text
cycle.analysis_datetime
cycle.background_datetime
cycle.window_begin
cycle.window_length
method.cost_type
method.covariance_date
arquivos de background
xtime dos backgrounds
observações dentro da janela
```

## 8. Bloco `geometry`

O bloco `geometry` define a geometria MPAS usada pela aplicação. Ele aponta para arquivos `namelist` e `streams`.

Exemplo conceitual:

```yaml
geometry:
  nml_file: ./namelist.atmosphere.outer
  streams_file: ./streams.atmosphere.outer
  deallocate non-da fields: true
  interpolation type: unstructured
```

No MPAS-JEDI, a geometria inicializa parte da infraestrutura do MPAS. Portanto, a existência dos arquivos referenciados no YAML não é suficiente: o runtime também precisa conter todos os arquivos que o MPAS espera resolver a partir de `namelist` e `streams`.

## 9. Geometria outer e inner

Em aplicações variacionais pode haver diferença entre a geometria da função custo e a geometria do inner loop. Em casos simples, ambas podem usar a mesma malha. Em casos avançados, pode haver dual-mesh ou dual-resolution.

Mesmo que o baseline inicial use uma única malha, o workflow deve permitir uma representação extensível:

```yaml
geometry:
  outer:
    mesh: x1.10242
    np: 64
    namelist: namelist.atmosphere.outer
    streams: streams.atmosphere.outer

  inner:
    mesh: x1.10242
    np: 64
    namelist: namelist.atmosphere.inner
    streams: streams.atmosphere.inner
```

Essa estrutura evita refatorações maiores quando forem adicionados experimentos com geometrias distintas entre outer e inner loop.

## 10. Arquivos obrigatórios de runtime MPAS

O diretório de runtime deve conter os arquivos que o MPAS-JEDI resolve em tempo de execução. Para o baseline `x1.10242`, exemplos importantes são:

```text
namelist.atmosphere.outer
streams.atmosphere.outer
namelist.atmosphere.inner
streams.atmosphere.inner
x1.10242.graph.info.part.64
x1.10242.invariant.nc
templateFields.10242.nc
stream_list.atmosphere.background
stream_list.atmosphere.analysis
stream_list.atmosphere.control
stream_list.atmosphere.ensemble
```

Além disso, o MPAS precisa de tabelas físicas e arquivos auxiliares, como:

```text
CAM_ABS_DATA.DBL
CAM_AEROPT_DATA.DBL
GENPARM.TBL
LANDUSE.TBL
OZONE_DAT.TBL
OZONE_LAT.TBL
OZONE_PLEV.TBL
RRTMG_LW_DATA
RRTMG_LW_DATA.DBL
RRTMG_SW_DATA
RRTMG_SW_DATA.DBL
SOILPARM.TBL
VEGPARM.TBL
```

O workflow deve preparar esses arquivos por links simbólicos sempre que possível, evitando cópias desnecessárias de dados grandes.

## 11. Consistência entre MPI, malha e decomposição

O número de processos MPI não é definido apenas no YAML. Ele precisa ser consistente entre:

```text
geometry.np
pbs.mpiprocs
launcher usado no PBS
arquivo graph.info.part.N
```

Exemplo de validação obrigatória:

```text
geometry.np = 64
pbs.mpiprocs = 64
arquivo x1.10242.graph.info.part.64 existe
comando de execução usa 64 processos MPI
```

Se qualquer uma dessas partes divergir, o workflow deve falhar antes da submissão.

## 12. Bloco `background`

O bloco `background` define o estado de primeira estimativa usado pela assimilação.

Exemplo conceitual:

```yaml
background:
  state variables:
  - u
  - v
  - theta
  - qv
  filename: ./background/mpasout.2018-04-14_21.00.00.nc
  date: 2018-04-14T21:00:00Z
```

O workflow deve validar:

- existência do arquivo de background;
- se o arquivo está no runtime ou linkado corretamente;
- se o `date` é coerente com o ciclo;
- se o `xtime` interno do NetCDF é coerente com o esperado;
- se as variáveis declaradas existem ou podem ser derivadas;
- se os arquivos cobrem a janela necessária ao 3D-FGAT.

## 13. Variáveis de estado, modelo e análise

O MPAS-JEDI diferencia variáveis de análise, variáveis de modelo e variáveis de estado/background.

O workflow deve validar a coerência entre:

```text
variables.yaml
stream_list.atmosphere.background
stream_list.atmosphere.analysis
arquivos NetCDF de background
geovars.yaml
operadores observacionais
```

Para o baseline atual, as variáveis de análise esperadas são compactas, normalmente relacionadas a vento zonal, vento meridional, temperatura, umidade específica e pressão à superfície.

As variáveis de estado/background podem ser mais numerosas e precisam estar compatíveis com o que o MPAS-JEDI espera ler e escrever.

## 14. Bloco `background error`

O bloco `background error` define a matriz B.

No baseline inicial, a covariância é `MPASstatic`. Isso não deve ser tratado apenas como uma string: essa escolha implica arquivos, variáveis, datas e transformações específicas.

O workflow deve validar:

```text
method.covariance_model
method.covariance_date
arquivos associados à B
variáveis de controle
variáveis de análise
geovars.yaml
compatibilidade com MPASstatic
```

Extensões futuras poderão incluir:

```text
SABER
BUMP
ensemble covariance
hybrid covariance
```

Essas extensões não devem quebrar o baseline MPASstatic.

## 15. Bloco `observations`

O bloco `observations` define os espaços observacionais usados na assimilação.

Estrutura conceitual:

```yaml
observations:
  observers:
  - obs space:
      name: Radiosonde
      obsdatain:
        engine:
          type: H5File
          obsfile: ./Data/obs/sondes_obs_2018041500.h5
      obsdataout:
        engine:
          type: H5File
          obsfile: ./Data/ombg/sondes_ombg_2018041500.h5
      simulated variables:
      - airTemperature
      - specificHumidity
      - windEastward
      - windNorthward
    obs operator:
      name: VertInterp
    obs error:
      covariance model: diagonal
    obs filters:
    - filter: Bounds Check
```

Cada observador deve ser validado individualmente.

O workflow deve checar:

```text
nome do observador
arquivo IODA de entrada
arquivo IODA de saída
variáveis simuladas
operador observacional
modelo de erro observacional
filtros
compatibilidade temporal com a janela
```

## 16. `obsdatain` e `obsdataout`

O `obsdatain` define o arquivo de observações usado como entrada.

O `obsdataout` define o arquivo gerado pelo JEDI com diagnósticos, equivalentes observacionais e informações úteis para avaliação posterior.

O workflow deve tratar `obsdataout` como parte importante do experimento, pois esses arquivos serão usados para:

- diagnóstico de OMB;
- diagnóstico de OMA;
- avaliação de filtros;
- comparação entre experimentos;
- cálculo de impacto de observações;
- relatórios científicos.

## 17. Operadores observacionais

O bloco `obs operator` define como o estado do modelo é transformado em equivalente observacional.

Exemplos:

```yaml
obs operator:
  name: VertInterp
```

ou, para radiâncias:

```yaml
obs operator:
  name: CRTM
```

Cada operador pode exigir variáveis específicas do estado, arquivos auxiliares ou configurações adicionais. A primeira versão do workflow deve validar a presença do operador. Validações específicas por operador devem ser adicionadas de forma incremental.

## 18. Filtros observacionais

Filtros são usados para controle de qualidade, rejeição, seleção de variáveis, seleção de canais, seleção espacial ou temporal e ajuste de erros.

Exemplo conceitual:

```yaml
obs filters:
- filter: Bounds Check
  filter variables:
  - name: airTemperature
  minvalue: 180.0
  maxvalue: 330.0
```

A primeira versão do workflow deve validar a estrutura dos filtros, sem tentar interpretar cientificamente todos os filtros disponíveis no JEDI/UFO.

## 19. Bloco `variational`

O bloco `variational` define a minimização.

Exemplo conceitual:

```yaml
variational:
  minimizer:
    algorithm: DRPCG
  iterations:
  - ninner: 10
    gradient norm reduction: 1.0e-10
```

No baseline atual, os parâmetros principais são:

```text
method.minimizer
method.ninner
method.gradient_norm_reduction
```

O workflow deve validar esses parâmetros de acordo com o perfil do experimento.

## 20. Blocos `final` e `output`

O bloco `final` controla ações ao fim da minimização, como avaliação final e escrita da análise.

O bloco `output` define arquivos de saída da análise ou incremento.

O workflow deve garantir que:

- diretórios de saída existam ou possam ser criados;
- nomes de arquivos sejam determinísticos;
- saídas não sejam versionadas no Git;
- saídas fiquem fora de `configs/`;
- logs e produtos de execução fiquem em diretórios apropriados.

## 21. Relação entre YAML, namelist, streams e runtime

No MPAS-JEDI, o YAML final não é suficiente. Ele aponta para arquivos `namelist` e `streams`, e esses arquivos determinam como o MPAS inicializa, lê e escreve campos.

O contrato operacional é:

```text
YAML geometry
  aponta para namelist e streams

namelist
  define opções internas do MPAS

streams
  define streams de entrada e saída

stream_list
  define variáveis lidas/escritas

background NetCDF
  precisa conter campos compatíveis

runtime
  precisa conter todos os arquivos resolvidos pelo MPAS
```

Erros em qualquer uma dessas camadas podem produzir falhas difíceis de diagnosticar. O workflow deve falhar cedo, com mensagens claras.

Exemplos de mensagens desejáveis:

```text
[ERROR] geometry.outer.namelist points to namelist.atmosphere.outer, but file is missing in runtime.
[ERROR] pbs.mpiprocs=64 but graph file x1.10242.graph.info.part.64 was not found.
[ERROR] background_state_variables contains theta, but stream_list.atmosphere.background does not include theta.
```

## 22. Validações mínimas para o baseline 3D-FGAT

### 22.1 Identidade do experimento

Validar:

```text
experiment.name
cycle.id
cycle.analysis_datetime
cycle.background_datetime
cycle.window_begin
cycle.window_length
method.cost_type
method.covariance_model
method.covariance_date
geometry.mesh
geometry.np
```

### 22.2 Runtime

Validar:

```text
runtime_dir existe ou pode ser criado
rendered_dir existe ou pode ser criado
required_directories são criados
required_links apontam para arquivos existentes
links não sobrescrevem arquivos reais
```

### 22.3 MPAS

Validar:

```text
namelist outer existe
streams outer existe
namelist inner existe
streams inner existe
graph.info.part.64 existe
invariant existe
templateFields existe
tabelas físicas existem
```

### 22.4 Background

Validar:

```text
arquivo de background existe
xtime esperado
campos obrigatórios
state variables compatíveis
```

### 22.5 Observações

Validar:

```text
observers esperados
arquivos IODA existem
simulated variables definidas
obs operator definido
obs error definido
obs filters estruturalmente válidos
```

### 22.6 PBS

Validar:

```text
mpiprocs compatível com np
launcher definido
executável JEDI existe
script PBS renderizado passa em bash -n
qsub não é executado automaticamente
```

## 23. Perfil de validação do baseline

O próximo passo recomendado é mover valores fixos do validador Python para um arquivo explícito:

```text
configs/experiments/3dfgat_mpastatic_x1.10242_2018041500/validation.yaml
```

Exemplo conceitual:

```yaml
validation:
  profile: strict_baseline

  expected:
    experiment_name: 3dfgat_mpastatic_x1.10242_2018041500
    cost_type: 3D-FGAT
    covariance_model: MPASstatic
    covariance_date: '2018-04-14T21:00:00Z'
    mesh: x1.10242
    np: 64
    mpiprocs: 64

    analysis_variables_count: 5
    model_variables_count: 30
    background_state_variables_count: 30

    observers:
      - Radiosonde
      - GnssroRefNCEP
      - SfcCorrected

    required_runtime_directories:
      - background
      - Data/os
      - Data/states
      - testinput

    required_background_fields:
      - ivgtyp
      - isltyp
      - landmask
      - znt
      - t2m
```

Esse arquivo torna o contrato científico do baseline explícito e facilita futuras generalizações sem remover proteção do caso funcional.

## 24. Arquitetura recomendada para validações futuras

A arquitetura de validação deve evoluir para responsabilidades separadas:

```text
monan_jedi_workflow/
  config/
    loader.py
    resolver.py
    schema.py

  validators/
    experiment.py
    runtime.py
    mpas.py
    observations.py
    variables.py
    covariance.py
    pbs.py

  render/
    jedi.py
    pbs.py
    templates.py

  runtime/
    staging.py
    checks.py

  sites/
    site.py
    registry.py

  diagnostics/
    yaml_compare.py
    runtime_report.py
```

A CLI deve permanecer fina. Ela deve apenas chamar as funções de alto nível, sem conter lógica científica diretamente.

## 25. Comandos desejados

A CLI deve evoluir gradualmente para suportar:

```bash
monan-jedi-workflow inspect-config <experiment>
monan-jedi-workflow validate-config <experiment>
monan-jedi-workflow prepare-runtime <experiment>
monan-jedi-workflow validate-runtime <experiment>
monan-jedi-workflow render-yaml <experiment>
monan-jedi-workflow render-pbs <experiment>
monan-jedi-workflow plan <experiment>
```

Futuramente, somente com autorização explícita:

```bash
monan-jedi-workflow submit <experiment>
```

## 26. Regra operacional

Nenhuma etapa do workflow deve submeter jobs automaticamente.

O workflow pode:

```text
validar
preparar runtime
renderizar YAML
renderizar PBS
gerar plano de execução
```

Mas não deve executar:

```bash
qsub
sbatch
mpiexec
mpirun
srun
```

sem autorização explícita do usuário.

## 27. Estratégia incremental

A evolução recomendada é:

1. preservar o baseline funcional;
2. documentar o contrato MPAS-JEDI;
3. explicitar o contrato em `validation.yaml`;
4. separar validação genérica de validação científica;
5. fortalecer validações de runtime;
6. adicionar suporte a sites;
7. refatorar renderização para templates;
8. adicionar novos experimentos sem alterar o núcleo do código.

A regra principal é: generalizar somente depois que o caso mínimo estiver documentado, validado e reproduzível.
