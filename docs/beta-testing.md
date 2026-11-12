# MONAN-JEDI 0.3.0b1 — beta para testes

Esta beta disponibiliza `obs`, `jedi`, `mpas`, `diagnostics` e `campaign`.
O pacote mantém os comandos legados. Cada app processa somente seu domínio em
um instante; o encadeamento é do simpleWorkflow ou de um shell do pesquisador.

## Instalar

```bash
git clone --branch feat/platform-domain-apps https://github.com/joaogerd/monan-jedi-workflow.git
cd monan-jedi-workflow
python -m pip install -e '.[dev]'
obs --help
jedi --help
mpas --help
diagnostics --help
campaign --help
```

Python >=3.10. JEDI, MPAS, WPS e Obs2IODA não são compilados por essa instalação.
Para gráficos, instalar `.[plots]`; para orquestração, usar o simpleWorkflow
0.6.2 já utilizado pelo grupo ou instalar `.[orchestration]`.
`environment-beta.yaml` oferece um ambiente conda com git e git-lfs.

## Teste imediato da instalação

```bash
cp -r examples/beta /tmp/monan-beta-test
bash /tmp/monan-beta-test/manual.sh /tmp/monan-beta-test/experiment.yaml 2025-09-01T00:00:00Z
```

**Esse exemplo usa produtos artificiais. Não executa JEDI, MPAS ou conversores
reais e não é evidência de resultado meteorológico.** O fixture instalado testa
comandos, arquivos, estados, validação e acesso ao catálogo fora do repositório.
O shell é um exemplo do usuário, não um executor de ciclo da plataforma.

Para testar a campanha, use uma cópia nova do exemplo (ou mude o destino para
não misturar o teste manual):

```bash
campaign inspect /tmp/monan-beta-test/campaign.yaml
campaign check /tmp/monan-beta-test/campaign.yaml
campaign export /tmp/monan-beta-test/campaign.yaml --engine simpleworkflow
swf validate /tmp/monan-beta-test/workflow.yaml
swf plan /tmp/monan-beta-test/workflow.yaml
swf run /tmp/monan-beta-test/workflow.yaml --ui plain
```

Inicialização única pode ser declarada separadamente, com outro principal se
necessário:

```yaml
initialization:
  - operation: mpas.init
    cycle: '2025-08-31T18:00:00Z'
    experiment: ./initialization-experiment.yaml
  - operation: mpas
    cycle: '2025-08-31T18:00:00Z'
    experiment: ./initialization-experiment.yaml
```

Ela é exportada em `initialization.tasks`, fora das tarefas repetidas. A receita
de inicialização precisa declarar insumos externos já preparados no formato
suportado pelo MPAS init; a beta não converte automaticamente qualquer análise
externa. Os comandos legados WPS permanecem disponíveis para a preparação de
insumos. `mpas.init` não é aceito na lista de operações repetidas.

O exportador gera um grafo explícito, com timestamps por tarefa nesta beta.
O simpleWorkflow executa e retoma o grafo. Ele é o único dono PBS nas tarefas
científicas que usam `site.execution.mode: pbs`. `campaign` não submete jobs,
não adquire observações e não chama o motor. ecFlow ainda não é suportado.

## Comandos e estados

| Verbo | Significado |
|---|---|
| inspect | Mostrar configuração efetiva, origem, entradas e produtos previstos |
| check | Conferir configuração e entradas disponíveis, sem preparar/processar |
| prepare | Materializar runtime e fotografia da configuração |
| run | Executar somente a operação preparada |
| validate | Verificar contrato dos produtos e registrar evidência |
| status | Consultar estado da operação |

Exemplos:

```bash
obs acquire inspect experiment.yaml --cycle 2025-09-01T00:00:00Z
obs convert prepare experiment.yaml --cycle 2025-09-01T00:00:00Z --source gpsro
jedi prepare experiment.yaml --cycle 2025-09-01T00:00:00Z
jedi run experiment.yaml --cycle 2025-09-01T00:00:00Z
jedi validate experiment.yaml --cycle 2025-09-01T00:00:00Z
mpas init prepare experiment.yaml --cycle 2025-09-01T00:00:00Z
mpas run experiment.yaml --cycle 2025-09-01T00:00:00Z
diagnostics run experiment.yaml --cycle 2025-09-01T00:00:00Z
```

Todos aceitam `--json`. `--source` é exclusivo OBS. `--engine` é exclusivo
`campaign export`. Sintaxe inválida retorna 2; falha de configuração, execução
ou validação retorna 1; sucesso retorna 0. `check` não garante disponibilidade
remota futura nem substitui os testes executados pelo programa científico.
Prepare não implica run; execução encerrada não implica produto validado.

## Arquivos do experimento

```yaml
schema_version: 1
experiment:
  name: meu-experimento
  destination: ./runs/meu-experimento
site: ./site.yaml
jedi: ./science/jedi.yaml
mpas: ./science/mpas.yaml
observations: ./science/jedi.yaml
cycle:
  interval: PT6H
diagnostics:
  run_dir: diagnostics/{cycle_id}
  cost_function:
    log: '{experiment_root}/jedi/{cycle_id}/jedi.stdout.log'
```

O principal referencia arquivos; não é necessário carregar JEDI/B ao usar MPAS
sozinho. `observations` pode apontar para arquivo próprio ou para `jedi.yaml`.
Em `mpas_init.validation.required_outputs`, paths relativos são relativos ao
runtime nesta interface. Receitas legadas que usavam paths relativos ao diretório
de configuração devem explicitá-los como absolutos ao migrar.

O arquivo científico contém os blocos nativos já suportados pelos estágios:
`jedi`, `mpas`, `mpas_init` e `obs2ioda`. O catálogo `catalog:...` é instalado no
pacote. Os principais refinados da proposta são uma direção de interface;
esta beta reutiliza os esquemas nativos efetivos, em vez de inventar traduções
científicas silenciosas. `examples/case` e `docs/configuration` documentam esses
esquemas. Não utilizar os templates marcados EDITAR sem completar a ciência.

Paths de fontes e templates são relativos ao YAML que os declara. `run_dir` e
`work_dir` são relativos ao destino do experimento. Campos que começam com uma
âncora de caminho, como `{experiment_root}`, são renderizados pelo contexto.
Variáveis de ambiente ausentes provocam erro. Variáveis declaradas de caminho
usadas como âncora devem resolver para paths absolutos. Não há avaliação de
código em expressões YAML; comandos/bootstrap explicitamente declarados são
executados como parte da operação.

O site pode ser compartilhado:

```yaml
site:
  execution:
    mode: pbs
  variables:
    monan_jedi_install_root: /caminho/instalacao
    stack_root: /caminho/stack
  resources:
    jedi:
      queue: fila-real
      select: 2
      ncpus: 64
      mpiprocs: 64
      walltime: '01:00:00'
```

Valores PBS explícitos do domínio prevalecem sobre o site. Recursos precisam
coincidir com o build, B e particionamento. A beta não define valores JACI
universais. Em modo PBS, `run` exige uma alocação existente (`PBS_JOBID`) e
executa o script preparado dentro dela. Não chama qsub. Para uso manual obtenha
uma alocação e ative o ambiente antes de chamar o worker. `mode: local` permite
execução sequencial com um processo, preservando bootstrap, setup e ambiente.

## Aplicação JEDI e seleção observacional

O bloco `jedi` pode conservar seus templates atuais. Alternativamente:

```yaml
jedi:
  # Os demais campos nativos: run_dir, background, pbs, validation etc.
  application: ./applications/3dfgat.yaml
  application_target: variational.yaml
  application_overrides:
    variational:
      iterations:
        - ninner: 10
observations:
  configure: ./ObsPlugs
  anchors: [ObsAnchors.yaml]
  use: [sondes, sfc, gnssrorefncep]
  products:
    sondes: {converter: prepbufr, acquisition: prepbufr}
    sfc: {converter: prepbufr, acquisition: prepbufr}
    gnssrorefncep: {converter: gpsro, acquisition: gpsro}
```

`application` é um documento JEDI nativo. Overrides de mapas são explícitos,
listas são substituídas inteiras e chaves de override inexistentes são recusadas.
A lista de outer loops usa a sintaxe do documento nativo escolhido; o exemplo
não declara que todos os builds têm o mesmo formato.

Cada nome seleciona `da/base/NOME.yaml` + `da/filters/NOME.yaml`. As âncoras
declaradas e os fragmentos são carregados como um documento, preservando a ordem
dos filtros. Os fragmentos devem conter blocos nativos de observer, não listas
ou templates NCAR ainda com placeholders não resolvidos. Os produtos associam
observers a conversores/fontes; itens não selecionados não bloqueiam a operação.
Receitas NCAR não são importadas/atualizadas automaticamente. Preserve commit,
licença, compatibilidade e adaptações ao incorporar uma receita científica.

`application_target` deve corresponder ao comando do executável variacional.
O estado T−3 da trajetória FGAT e o estado completo T usado como base da análise
continuam sendo contratos distintos do bloco nativo. Não mudar loops, filtros,
passo, B ou física junto da validação da migração.

## Aquisição e conversão

```yaml
acquisition:
  sources:
    - name: gpsro
      source: 'https://servidor/arquivo.{cycle_yyyymmddhh}.bufr'
      destination: raw/{cycle_id}/gpsro.bufr
      # sha256: digest esperado, quando disponível
```

Aquisição suporta arquivo local e HTTP(S) direto, com publicação atômica,
checagem de tamanho e checksum opcional. Arquivos externos existentes não são
sobrescritos. Produtos já publicados por uma tentativa da própria operação
podem ser reutilizados na retomada após verificar seu hash. Arquivos arquivados
que precisam de extração continuam exigindo preparação externa ou a rota legada
já existente; a beta não promete suporte a todo provedor.

`obs2ioda` conserva o schema nativo de conversores, argv, inputs, outputs,
inspection e runtime. A inspeção IODA é configurável e executada em validate.
Cada --source tem seu próprio runtime/manifesto. Exigir produtos para cada
observer selecionado faz parte da receita; fonte ausente provoca erro explícito.

## Diagnósticos

`cost_function.log` extrai os valores de J. Pode declarar `pattern` como regex
com um grupo capturando o número, para o formato real de log. Nenhum registro
válido provoca erro; não é apresentado como sucesso vazio. `plots: true` grava
PNG com matplotlib; resumo JSON e tabela CSV não dependem do extra gráfico.

Para departures IODA:

```yaml
diagnostics:
  run_dir: diagnostics/{cycle_id}
  departures:
    files: ['{experiment_root}/jedi/{cycle_id}/obsout.nc4']
    groups: {background: ombg, analysis: oman}
```

A beta calcula N, viés e RMSE de valores finitos por variável e grupo, verifica
unidades e não mistura variáveis numa média única. O arquivo deve conter as
departures nos grupos declarados; a beta não transforma HofX em departures
implicitamente. A seleção/QC precisa estar aplicada ou documentada na entrada.
Esses resultados não constituem avaliação independente de habilidade.

## Retomada e proteção

A fotografia em `.platform/CICLO/APP-OPERACAO` preserva configuração, origem,
identidade, tentativas e hashes. O runtime efetivo tem dono e lock próprios,
impedindo que outro ciclo/experimento use o mesmo diretório para escrita.
Falhas liberam locks; processos interrompidos não exigem apagar locks manualmente
(flock é liberado pelo sistema). Um runtime já ocupado sem identidade é recusado.

Uma tentativa interrompida enquanto estava `running` é recusada para nova
execução automática: confira o processo/job anterior antes de usar outro destino.
Logs de workers anteriores são preservados dentro do runtime.

Mudanças de configuração/entradas recusam reutilização: crie novo destino. A
beta não tem --force para apagar ciência anterior. SHA256 de arquivos de entrada,
executáveis identificados, templates e assets pode custar I/O em bases grandes;
a beta prioriza detectar mudanças sobre atalhos silenciosos de reuso.

## Aceitação na JACI

1. Criar um destino novo e copiar a receita científica de referência efetiva.
2. Conferir `inspect/check`, paths, malha/níveis, ranks/B, estado T−3 e estado T.
3. Preparar cada operação e comparar configurações geradas com a referência.
4. Executar um ciclo por tarefas do simpleWorkflow, com um único dono PBS.
5. Conferir validações, estados NetCDF, logs, IODA e diagnósticos.
6. Exercitar uma retomada antes de ampliar para sete ou trinta dias.

A beta foi construída para esses testes. A execução real na JACI e a
equivalência numérica da referência não são substituídas pelo fixture local.

## Evidência local desta entrega

- 222 testes passaram (7 avisos já presentes na base).
- Wheel instalado em ambiente separado; os cinco apps executaram o fixture fora do checkout.
- simpleWorkflow 0.6.2 validou e executou 30 tarefas: 3 de inicialização e 27 em dois horários.
- Fixture artificial: sem alegação de equivalência numérica ou validação HPC.
