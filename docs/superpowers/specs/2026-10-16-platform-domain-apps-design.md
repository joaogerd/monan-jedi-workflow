# Proposta da plataforma MONAN-JEDI

**Versão:** 0.3 — contrato de comandos aprovado — 16 de outubro de 2026  
**Objetivo imediato:** fechar a arquitetura e entregar uma beta utilizável sobre as capacidades existentes.  
**Estado deste documento:** proposta de comportamento e interfaces; os comandos e YAMLs novos abaixo ainda não constituem funcionalidades implementadas ou verificadas.

## 1. Resultado pretendido e decisões aprovadas

O `monan-jedi-workflow` será a plataforma de trabalho do pesquisador, distribuindo cinco aplicações: `obs`, `jedi`, `mpas`, `diagnostics` e `campaign`, além de APIs, configurações, exemplos e documentação.

Cada aplicação executa somente operações do seu domínio para o instante solicitado. Não existe comando de ciclo completo, compositor interno de execução nem laço de campanha. O orquestrador encadeia as operações e controla o calendário. Um usuário pode escrever um shell para encadear os mesmos comandos manualmente.

```bash
jedi run experiment.yaml --cycle 2025-09-01T00:00:00Z
```

Esse comando executa somente a assimilação em T, a partir do runtime preparado. Não adquire observações, não prepara o runtime implicitamente, não inicia MPAS e não gera diagnósticos automaticamente.

Instalar a plataforma disponibiliza apps e catálogo. Executáveis científicos, bases observacionais, malhas e B são dependências declaradas e verificadas; não são todos baixados ou compilados automaticamente. O perfil JACI aponta para instalações e áreas do grupo.

## 2. Precedência dos contextos

Ordem: decisões desta conversa; refinamento de configuração de 16/10; Contexto Geral de 12/10 como base arquitetural. A cronologia esclarecida por João prevalece sobre nomes e cabeçalhos dos arquivos.

A organização é `experiment.yaml` como entrada principal, `jedi.yaml` para assimilação e observações, `mpas.yaml` para modelo e site compartilhado para infraestrutura. O calendário fica em `campanha.yaml`.

A aprovação do contrato de comandos não transforma exemplos de schema ou funcionalidades propostas em implementação existente.

## 3. Arquitetura escolhida

Um pacote integrado fornece apps e APIs de domínio independentes. O catálogo é distribuído como recurso instalado. O MPAS reutiliza capacidades do mpaswf por adaptador. Separar pacotes desde o início aumentaria a coordenação de versões sem benefício comprovado para a beta.

O módulo de orquestração descreve tarefas e exporta configurações; não executa o grafo. simpleWorkflow é o motor padrão. ecFlow será um exportador posterior, sem duplicar regras científicas.

## 4. Responsabilidades

| App | Responsabilidade | Limite |
|---|---|---|
| `obs` | Aquisição, conversão e validação observacional | Não executa assimilação |
| `jedi` | Preparação, execução e validação da assimilação | Não executa previsão |
| `mpas` | Inicialização e previsão | Não avança ciclos de AD |
| `diagnostics` | Diagnósticos, avaliação e comparação | Não refaz operações científicas |
| `campaign` | Inspeção, verificação e exportação da campanha | Não executa campanha |

Configuração, contratos de artefatos e integração de execução são serviços compartilhados. Estado operacional do motor e evidência científica permanecem separados.

## 5. Contrato comum de comandos — aprovado

| Verbo | Significado | Efeito |
|---|---|---|
| `inspect` | Mostrar configuração efetiva, entradas, saídas e ações previstas | Apenas leitura |
| `check` | Conferir configuração, dependências e entradas necessárias | Não prepara nem executa |
| `prepare` | Materializar configurações, diretórios e links da operação | Grava runtime; não processa |
| `run` | Executar a operação preparada e registrar a tentativa | Executa somente aquela operação |
| `validate` | Conferir produtos contra o contrato declarado | Grava relatório de validação |
| `status` | Mostrar situação, tentativa e produtos | Apenas leitura |

`check` verifica condições de entrada; `validate` verifica resultados. `run` não faz preparação oculta. Terminar `run` com sucesso significa execução encerrada; liberar o produto para consumo depende de `validate`.

O conjunto de verbos é aplicado quando faz sentido. Não se criam comandos vazios para obter simetria. No `campaign`, os verbos iniciais são `inspect`, `check` e a ação específica `export`; não há `campaign run`.

### Sintaxe

```text
APP VERBO CONFIG --cycle T
APP OPERAÇÃO VERBO CONFIG --cycle T
```

Operações especializadas vêm antes do verbo. A raiz `jedi` representa assimilação; a raiz `mpas`, previsão; `mpas init`, inicialização. OBS explicita aquisição ou conversão, sem um `obs run` que combine as duas.

### Padrões transversais

- Arquivo de configuração como argumento posicional; mesmo `--cycle` e seletores equivalentes com o mesmo nome.
- Tempos explícitos em UTC; processamento científico não aceita início/fim de campanha.
- Mensagens com app, operação, ciclo, resultado e localização dos logs.
- `--json` oferece saída estruturada equivalente à apresentação humana.
- Categorias equivalentes de falha usam os mesmos códigos de saída, definidos numa tabela central antes da implementação.
- Nenhum comando inicia outro domínio ou avança calendário implicitamente.
- Inspeção não baixa dados nem submete jobs; validação grava seu próprio relatório.

## 6. Exemplos de uso

### Assimilação, previsão e diagnósticos

```bash
jedi inspect experiment.yaml --cycle T
jedi check experiment.yaml --cycle T
jedi prepare experiment.yaml --cycle T
jedi run experiment.yaml --cycle T
jedi validate experiment.yaml --cycle T
jedi status experiment.yaml --cycle T
```

O mesmo percurso usa `mpas` para previsão e `diagnostics` para gerar diagnósticos do ciclo. A agregação de resultados existentes pode usar uma operação especializada, sem executar ciclos.

### Operações especializadas

```bash
obs acquire prepare experiment.yaml --cycle T
obs acquire run experiment.yaml --cycle T
obs acquire validate experiment.yaml --cycle T
obs convert prepare experiment.yaml --cycle T
obs convert run experiment.yaml --cycle T
obs convert validate experiment.yaml --cycle T
mpas init prepare experiment.yaml --cycle T
mpas init run experiment.yaml --cycle T
mpas init validate experiment.yaml --cycle T
```

`inspect`, `check` e `status` também se aplicam a essas operações. Seletores como `--source gpsro` restringem a operação sem mudar o significado do verbo. T é um marcador didático; o comando real recebe uma data UTC.

### Campanha

```bash
campaign inspect campanha.yaml
campaign check campanha.yaml
campaign export campanha.yaml --engine simpleworkflow
```

`export` grava a configuração do motor, sem executar dados ou jobs. O calendário e as dependências entre ciclos pertencem ao orquestrador.

### Execução HPC

Workers executam dentro da alocação apropriada, bloqueando até o término da operação. `run` não submete silenciosamente nem inicia MPI no login. O preflight verifica o contexto de execução.

No uso manual, a alocação é obtida explicitamente. Na integração nova, motor/adaptador é o único dono PBS. O backend legado submit/wait pode permanecer durante a migração, explicitamente identificado; nunca haverá duas camadas submetendo a mesma operação.

## 7. Uma entrada principal, configurações por responsabilidade

O usuário fornece `experiment.yaml` aos comandos. Esse principal referencia arquivos científicos claros, conforme o refinamento de 16/10. Uma entrada de CLI não significa um único arquivo editável: para mudar loops ou seleção observacional, o cientista edita `jedi.yaml`; para mudar previsão ou física, edita `mpas.yaml`.

| Arquivo | Conteúdo | Quando editar |
|---|---|---|
| `experiment.yaml` | Nome, destino, referências, contrato de ciclo e entradas | Criar ou recompor o experimento |
| `jedi.yaml` | Método, janela, loops, B, variáveis e seleção OBS | Alterar assimilação ou observações |
| `mpas.yaml` | Malha, integração, física, inicialização e saídas | Alterar o modelo ou a previsão |
| Site compartilhado | Instalação, raízes, módulos, launcher, filas e recursos | Configurar o ambiente |
| Catálogo | Aplicações, operadores, filtros, templates e receitas | Ajustes especializados ou manutenção |
| `campanha.yaml` | Período e política de orquestração | Executar uma sequência de ciclos |

O refinamento anterior colocava período em `experiment.yaml`. Aqui esse ponto é ajustado à orientação mais recente: o período fica no arquivo operacional da campanha. A separação entre os arquivos científicos é preservada.

Exemplos conceituais, sujeitos ao schema final. Receitas e paths ilustram contratos propostos; não comprovam disponibilidade atual. Os arquivos abaixo ficam juntos no diretório do experimento. O catálogo é um recurso instalado; `catalog:` é uma URI proposta para identificá-lo sem depender do checkout.

### `experiment.yaml`

```yaml
schema_version: 1
experiment:
  name: setembro-2025
  destination: ./runs/setembro-2025
site: catalog:sites/jaci
jedi: ./jedi.yaml
mpas: ./mpas.yaml
cycle:
  interval: PT6H
inputs:
  background:
    mode: explicit
    trajectory_start: "${BACKGROUND_ROOT}/mpasout.{window_start_mpas}.nc"
    analysis_state: "${BACKGROUND_ROOT}/mpasout.{cycle_mpas}.nc"
diagnostics:
  use: [cost_function, observation_departures]
```

### `jedi.yaml`

```yaml
schema_version: 1
assimilation:
  recipe: catalog:jedi/reference-2025-fgat
  window:
    before: PT3H
    after: PT3H
  minimization:
    algorithm: DRPCG
    outer_loops:
      - inner_iterations: 10
        gradient_norm_reduction: 1.0e-10
  background_error:
    configuration: catalog:jedi/covariance/reference-2025
    directory: "${BMATRIX_ROOT}"
observations:
  configure: catalog:jedi/ObsPlugs
  use: [sondes, sfc, gnssrorefncep]
  input:
    mode: convert
    sources: catalog:observations/sources/reference-2025
```

### `mpas.yaml`

```yaml
schema_version: 1
mpas:
  recipe: catalog:mpas/reference-2025
  forecast:
    duration: PT6H
    state_interval: PT3H
```

A receita do modelo resolve malha, física, passo de tempo e templates, todos visíveis na inspeção. Overrides suportados devem ser documentados no template completo; não se inventam valores para preencher o exemplo curto. A inicialização externa é declarada no bloco MPAS quando necessária, com formato, fonte e tempo explícitos.

### `site.yaml` compartilhado

O perfil JACI reúne caminhos da instalação, Spack/módulos, launcher MPI, filas e recursos por aplicação. Ambiente específico do Obs2IODA fica restrito ao conversor. O pesquisador pode apontar para um site local por caminho, em vez de uma entrada do catálogo.

### O que o resolvedor produz

O resolvedor lê os arquivos referenciados, valida suas fronteiras e gera uma configuração efetiva única por execução. Esse produto é uma fotografia para inspeção e reprodução, não mais um principal que o usuário deve editar.

Não há start/end no experimento. `interval` exprime a relação científica esperada entre análises e produtos; o calendário da campanha deve ser coerente com ele. O modo `explicit` recebe estados existentes. Outro modo, `cycle_products`, resolve os artefatos do ciclo anterior por manifesto; o orquestrador deve exigir sua produção antes de iniciar o consumidor. O primeiro ciclo precisa de entradas externas explicitamente associadas.

Tempos são derivados exclusivamente de T e das durações declaradas. Variáveis de ambiente usam lista permitida; variáveis ausentes falham. Placeholders de datas são fechados e documentados. Não se avalia código contido no YAML.

### Regras de resolução

- Paths locais são relativos ao arquivo que os declara; paths de saída são normalizados e mostrados na inspeção.
- Site fornece instalação, recursos e raízes; receitas fornecem a ciência; ajustes em `jedi.yaml` e `mpas.yaml` só substituem campos permitidos pelo schema. O principal não redefine silenciosamente os blocos referenciados.
- Campos desconhecidos, receitas inexistentes e conflitos provocam erro antes da submissão.
- Listas de observers, filtros, outer loops e blocos SABER têm ordem preservada; sua substituição é explícita, sem merge posicional implícito.
- Configurações especializadas podem ser referenciadas localmente. A autonomia científica permanece disponível.
- O lock preserva conteúdo e hashes das receitas, configurações geradas, versões conhecidas e overrides. Um nome de receita sem hash não garante reprodução.
- Inspeção resolve configuração sem adquirir dados ou submeter jobs. Preparação grava o runtime e seus metadados.
- A seleção observacional determina produtos e conversores exigidos. ASCAT não selecionado não bloqueia a análise por estar vazio.

## 8. Catálogo observacional e ciência preservada

Manter `observations.configure` para configurações e `directory` para dados. A seleção `sondes`, `sfc`, `gnssrorefncep` resolve base, filtros e dependências compartilhadas do catálogo.

O resolvedor de configuração deve montar o documento completo antes de resolver âncoras YAML. Fragmentos NCAR podem depender de aliases e substituições; não devem ser tratados como documentos independentes prontos.

Cada receita registra origem, commit, atribuição/licença, compatibilidade e adaptações. Atualizar o catálogo não altera silenciosamente uma execução materializada. O formato nativo JEDI permanece visível nos detalhes científicos.

A beta deve conservar o perfil da referência de setembro de 2025 descrita no Contexto Geral. O caso M3/2018 é uma referência histórica distinta e pode ser usado como fixture documental, sem misturar seus IODA iniciais, inicialização ou contagens de tarefas com 2025.

Não alterar simultaneamente filtros, minimizador, SST, física e arquitetura. A referência documentada usa um outer e dez inner; esse fato não significa que sejam parâmetros otimizados. Mudanças científicas terão experimentos próprios depois da equivalência arquitetural.

## 9. Contrato temporal FGAT

Para uma análise às 06Z, com janela ±3h:

| Produto | Validade | Papel |
|---|---|---|
| Forecast anterior | 03Z | Estado inicial da trajetória nonlinear FGAT |
| Forecast anterior | 06Z | Estado completo sobre o qual a análise será escrita |
| Integração interna JEDI | 03Z–09Z | Trajetória dentro da janela observacional |
| Análise JEDI | 06Z | Estado analisado completo |
| Forecast pós-análise | 09Z e 12Z | Insumos para o ciclo de 12Z |

A integração interna JEDI e a previsão externa são operações diferentes. O estado em 03Z não substitui o estado completo em 06Z.

Passos de tempo outer, inner e forecast pertencem à receita. Não impor igualdade universal: o Contexto Geral registra outer/forecast de 1200 s e inner de 1800 s na referência de 240 km. Validadores devem aplicar o contrato específico da receita e verificar tempos realmente presentes.

B, geometria, níveis e particionamento são um conjunto compatível. Em B com arquivos locais NICAS/sampling, mudar ranks exige verificar a decomposição suportada. Selecionar 15 km não pode disparar procura por insumos de 240 km.

## 10. Modelo independente com análise externa

O mesmo app MPAS pode executar uma previsão sem qualquer assimilação. Um experimento desse tipo declara apenas site, receita de modelo, duração e entrada externa.

O contrato distingue dois formatos de entrada:

- Estado MPAS pronto e compatível: validação direta e preparação do forecast.
- Análise externa em formato aceito pelo backend existente: aquisição/preprocessamento explícitos, MPAS init e validação antes do forecast.

Não prometer suporte genérico a qualquer análise externa. O catálogo lista formatos e provedores efetivamente suportados. Na beta, reutilizar somente a rota já existente e verificável no mpaswf.

```bash
mpas init prepare previsao.yaml --cycle 2025-09-01T00:00:00Z
mpas init run previsao.yaml --cycle 2025-09-01T00:00:00Z
mpas init validate previsao.yaml --cycle 2025-09-01T00:00:00Z
mpas prepare previsao.yaml --cycle 2025-09-01T00:00:00Z
mpas run previsao.yaml --cycle 2025-09-01T00:00:00Z
mpas validate previsao.yaml --cycle 2025-09-01T00:00:00Z
```

O leitor MPAS não exige B, UFO, observações nem referência `jedi` num experimento exclusivo de previsão. Analogamente, o percurso OBS exige apenas a seção observacional de `jedi.yaml`, sem validar B ou método de assimilação não utilizados.

## 11. Campanha e simpleWorkflow

A campanha aponta para o experimento e declara o calendário. É um arquivo operacional adicional, mantido por quem organiza a campanha; o pesquisador mantém um principal de entrada e arquivos científicos separados por responsabilidade.

```yaml
schema_version: 1
experiment: ./experiment.yaml
calendar:
  start: "2025-09-01T00:00:00Z"
  end: "2025-09-08T00:00:00Z"
  interval: PT6H
  end_inclusive: true
last_cycle:
  forecast: false
engine: simpleworkflow
```

Essa campanha produz 29 análises e 28 previsões entre análises, se a inicialização tiver sido fornecida/planejada separadamente. O exportador deve explicar a convenção inclusiva e listar as instâncias antes de gravar o workflow.

```bash
campaign inspect campanha.yaml
campaign export campanha.yaml
```

O exportador não executa dados ou jobs. O usuário usa o workflow gerado com a interface própria do simpleWorkflow. A sintaxe exata dessa chamada será documentada após conferir a versão instalada.

**Granularidade recomendada:** o exportador descreve tarefas de aquisição, conversão, preparação, execução e validação. Uma conversão pode ser refeita sem repetir JEDI e MPAS. O motor e as chamadas manuais usam as mesmas APIs e contratos; a plataforma não executa esse grafo.

A descrição intermediária contém tarefas, artefatos, tempos, recursos e dependências. O exportador traduz essa descrição. O ecFlow futuro recebe a mesma descrição; não ganha uma segunda definição de ciência.

## 12. Organização proposta

Árvore de responsabilidades; criar módulos conforme necessidade, sem scaffolding vazio.

```text
monan-jedi-workflow/
├── pyproject.toml
├── config/
│   ├── sites/
│   ├── observations/{sources,converters}/
│   ├── jedi/
│   │   ├── applications/
│   │   ├── variables/
│   │   ├── covariance/
│   │   └── ObsPlugs/da/{base,filters,bias,filtersWithBias}/
│   └── mpas/{meshes,physics,templates}/
├── monan_jedi_workflow/
│   ├── cli/
│   ├── configuration/
│   ├── core/                 # contextos, artefatos e contratos
│   ├── observations/
│   ├── assimilation/
│   ├── model/                # adaptador mpaswf
│   ├── diagnostics/
│   ├── execution/            # contexto HPC/adaptadores
│   └── orchestration/        # descrição e exportadores
├── examples/{observations-only,analysis-only,forecast-only,single-cycle,campaign}/
├── docs/
└── tests/
```

Não é necessário migrar imediatamente para layout `src/`. O catálogo deve integrar o pacote instalado como recurso, sem depender do diretório corrente ou de um clone permanente.

```text
meu-trabalho/
├── experiment.yaml               # entrada principal
├── jedi.yaml                      # assimilação e observações
├── mpas.yaml                      # modelo e previsão
├── campanha.yaml                 # somente quando houver campanha
└── runs/setembro-2025/
    ├── configuration/            # original, resolvido, lock e proveniência
    ├── initialization/
    ├── orchestration/simpleworkflow/
    ├── cycles/20250901T000000Z/
    │   ├── plan.json
    │   ├── obs/
    │   ├── analysis/
    │   ├── forecast/
    │   ├── diagnostics/
    │   └── manifest.json
    └── diagnostics/               # agregação de produtos existentes
```

Cada operação preserva tentativas, logs, configuração gerada e validação. Dados grandes podem ficar em áreas compartilhadas por referência. O estado interno do simpleWorkflow continua pertencendo ao motor e respeita seu layout.

## 13. Produtos, falhas e retomada

Um produto é consumível após validação e publicação do manifesto correspondente. Existência do arquivo, fim do job ou exit code zero não bastam.

O manifesto registra T, janela, papéis e tempos das entradas, configuração efetiva, identificadores/hashes, versões conhecidas, executável, produtos e critérios de validação. Campos desconhecidos ficam identificados como desconhecidos, sem alegar reprodução estrita.

O estado operacional registra tentativa, job ID, logs e retorno. Não se confunde com o estado científico. Execução manual não altera diretamente o banco do orquestrador.

Repetição compatível pode reaproveitar produtos se entradas, configuração, executáveis e contratos coincidirem e continuarem válidos. Alteração de QC/B/receita gera incompatibilidade: a operação exige nova identidade de execução ou decisão explícita de recomputar. Não sobrescreve resultados científicos anteriores silenciosamente.

Locks por operação impedem dois workers de escrever no mesmo runtime. Um lock abandonado exige verificar processo/job antes de liberar. Downloads usam destino temporário e publicação atômica após validação.

Exemplo de erro desejado:

```text
ANÁLISE / preparação / 2025-09-01 06 UTC
Falta o estado completo em 06 UTC.
Encontrado: somente estado de trajetória em 03 UTC.
Origem: inputs.background.analysis_state
Nenhum job foi iniciado. Confira os produtos do forecast anterior.
```

## 14. Estudo mental de funcionamento

Estes percursos são exercícios de consistência, não testes executados.

| Cenário | Percurso e comportamento esperado |
|---|---|
| Somente observações | OBS adquire, converte e valida; não exige B ou executável JEDI |
| Análise isolada | JEDI recebe IODA, B e estados prontos; não adquire dados nem inicia forecast |
| Ciclo completo manual | O pesquisador executa os comandos separados ou escreve um shell; a plataforma não fornece um executor de ciclo |
| Previsão livre | MPAS init prepara análise externa suportada; MPAS executa uma previsão, sem exigir JEDI/OBS |
| Campanha de sete dias | campaign export gera tarefas; simpleWorkflow instancia 29 análises e 28 forecasts quando o último forecast é desabilitado |
| GPSRO falha no quarto dia | Refazer só a conversão selecionada e retomar pelo motor; produtos anteriores válidos permanecem |
| Filtro alterado | Configuração incompatível invalida reuso; criar nova execução ou recomputar explicitamente |
| Resolução de 15 km | Validar malha, níveis, B, partições e passos; não procurar insumos de 240 km por fallback |
| Job termina sem análise completa | run registra o retorno; validate falha e consumidores não são liberados |
| Manual concorre com motor | Lock impede escrita concorrente no mesmo runtime |
| Background intermediário ausente | Falha localizada; não reinicializar silenciosamente com GFS |
| Instalação fora do clone | Apps encontram catálogo instalado e check aponta dependências ausentes |

### Encadeamento manual ilustrativo

Dentro do ambiente apropriado, um shell do próprio pesquisador pode chamar aquisição, conversão, JEDI, MPAS e diagnósticos, com prepare/run/validate em cada operação e interrupção no primeiro erro. Esse shell não faz parte de um compositor oculto da plataforma. O orquestrador usa as mesmas operações e acrescenta calendário, dependências e controle operacional.

## 15. Beta a entregar hoje: recorte proposto

A meta de hoje deve ser uma beta funcional de integração, construída sobre o que já funciona. Entregar de uma vez todos os conversores, resoluções, métodos e motores seria um compromisso sem base. O prazo é uma meta; a conclusão depende da inspeção do código atual e da disponibilidade de execução real na JACI.

| Obrigatório para a beta | Limite |
|---|---|
| Principal + JEDI + MPAS + site e catálogo distribuído | Um perfil científico validável de referência |
| `obs`, análise JEDI e MPAS independentes | Reutilizar backends existentes |
| `jedi run --cycle` | Somente assimilação, sem executar outros domínios |
| MPAS independente | Uma rota de análise externa já suportada |
| Diagnósticos do ciclo | J e departures já disponíveis; declarar alcance |
| Inspeção e preflight | Configuração, tempos, entradas e dependências |
| Exportação simpleWorkflow | Tarefas chamam os mesmos comandos usados manualmente |
| Logs, validação e retomada | Sem sobrescrita ou reuso incompatível |
| Exemplos comentados e instalação | Um ambiente suportado explicitamente |

**Depois da beta:** ecFlow executável, novos observers/radiâncias, novos formatos externos, ajustes de loops, SST, híbrido, interface web e campanhas de 30 dias/um ano.

### Sequência de trabalho para 16/10

| Bloco | Entrega concreta | Evidência de saída |
|---|---|---|
| 1. Fechar interfaces e inspecionar repositório | Schema mínimo, semântica de comandos, backend PBS e referência escolhida | Mapa entre proposta e código existente |
| 2. Provar configuração + uma operação | Catálogo instalado, resolução e runtime de referência | Comparação com configuração efetiva histórica |
| 3. Completar percurso vertical | OBS → análise → forecast → diagnóstico para um T | Testes de contratos e execução controlada |
| 4. Ligar simpleWorkflow | Exportação do mesmo grafo | Dependências e comandos conferidos |
| 5. Exercitar falhas e empacotar | Exemplos, changelog, instalação e limitações | Relatório curto de aceitação |

Essa sequência orienta a priorização; o plano de implementação com arquivos e verificações depende da revisão desta proposta e do código atual.

## 16. Critérios verificáveis de aceitação

1. Instalação limpa encontra apps e catálogo sem depender do diretório do repositório.
2. O conjunto comentado `experiment.yaml` + `jedi.yaml` + `mpas.yaml` + site reproduz a configuração científica escolhida; a configuração efetiva preserva a origem de cada valor e as diferenças justificadas de caminhos/metadados.
3. `jedi run` exige um T e executa somente assimilação; nenhum app executa o ciclo completo ou contém laço de campanha.
4. Análise, OBS e modelo funcionam isoladamente com validação apenas de suas dependências.
5. Uso manual e workflow exportado chamam as mesmas operações, com verbos, argumentos e contratos equivalentes.
6. Uma campanha de 01–08/09 a cada 6h enumera 29 análises e 28 previsões quando selecionado o último ciclo sem forecast.
7. T−3 e T são verificados por papel e validade; trocar esses arquivos provoca falha.
8. Fonte obrigatória ausente falha; fonte não selecionada não bloqueia.
9. Mudança científica invalida reuso; repetição compatível evita execução desnecessária.
10. Concorrência e produto parcial não publicam sucesso.
11. Cada job tem um único dono PBS e logs acessíveis por operação.
12. Há evidência de um ciclo real em diretório separado na JACI antes de chamar a beta de validada em HPC.

Testes com backends simulados verificam integração de software, mas não substituem o item 12. Sem acesso HPC disponível, a entrega deve ser identificada como beta de software aguardando validação no ambiente, com essa pendência explícita.

## 17. Decisões aprovadas e pontos técnicos restantes

Aprovados nesta conversa:

- Cinco apps: obs, jedi, mpas, diagnostics e campaign.
- Cada domínio executa apenas sua operação, sem compositor de ciclo completo.
- Encadeamento pelo orquestrador ou shell escrito pelo usuário.
- Verbos comuns inspect, check, prepare, run, validate e status, quando aplicáveis.
- Operações especializadas precedem o verbo; campaign export gera configuração sem executar campanha.
- Principal experiment.yaml, arquivos jedi.yaml/mpas.yaml e site compartilhado.

Pontos técnicos a fechar na inspeção do código: schema definitivo, URIs do catálogo, tabela numérica de erros, payload JSON, versões dos backends, contrato de alocação e migração de submit/wait. Não alteram a divisão aprovada.

## 18. Base documental e limites

Fontes lidas: Contexto_Geral_MONAN_JEDI_2026-10-16.md, base geral de 12/10 segundo João, e Contexto_Configuracao_MONAN_JEDI(1).md, refinamento de 16/10 segundo o mesmo esclarecimento.

O Contexto Geral registra a captura histórica de setembro de 2025: 29 análises, 28 forecasts, 29 conversões, 502 estados de tarefas em sucesso e 59 jobs. Esses números não foram revalidados aqui no HPC. A contagem de tarefas pode mudar sem alterar a ciência; equivalência deve comparar configurações, entradas, relações temporais e produtos.

O caso M3/2018 permanece distinto da referência de setembro de 2025. Não misturar seus dados iniciais ou contagens. Receitas NCAR precisam preservar origem, commit, atribuições, ordem dos filtros e adaptações deliberadas.

Não houve implementação, atualização JACI ou alteração científica nesta etapa. Os comandos documentados são contratos do desenho a implementar.

## 19. Revisão 0.3

Esta revisão substitui o compositor de ciclo das versões anteriores pela divisão aprovada de domínios. Retira jedi analysis, jedi diagnostics, jedi campaign e o modo de execução analysis_only: assimilação é jedi, diagnóstico é diagnostics e exportação é campaign. A ausência de forecast no último instante é uma decisão explícita da campanha, não um modo de execução do app JEDI.

A meta original de beta em 16/10 permanece registrada como intenção, não como entrega realizada. A conclusão exige os critérios de aceitação e evidência de execução apropriada.
