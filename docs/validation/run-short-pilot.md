# Executar o piloto científico na JACI

Objetivo: JEDI 01/09/2025 00Z → MPAS 00Z (+3 h/+6 h) → JEDI 06Z.
Usa os IODA históricos para isolar a validação da plataforma. Não faz aquisição,
conversão ou inicialização nova. O segundo JEDI usa a previsão do candidato.

## Instalar a entrega

Copiar o pacote `monan-jedi-beta-scientific-pilot.tar.gz` para a JACI. Extrair
em um diretório novo em `/p`, ativar o ambiente MONAN-JEDI já usado na referência
e instalar o código extraído nesse ambiente:

```bash
export VALIDATION_WORK=/p/projetos/monan_das/${USER}/work/beta-validation-20261112
mkdir -p "$VALIDATION_WORK"
tar -xzf monan-jedi-beta-scientific-pilot.tar.gz -C "$VALIDATION_WORK"
python -m pip install --no-deps --no-build-isolation -e "$VALIDATION_WORK/monan-jedi-workflow"
python -c 'import sys, yaml, netCDF4, numpy; print(sys.executable)'
```

O Python e o ambiente precisam estar em `/p`, visíveis nos nós de computação.
Usar o mesmo stack, executáveis e ambiente científico da referência. Devem
estar definidos `MONAN_JEDI_INSTALL_ROOT`, `STACK_ROOT` e `USER`.
O preflight exige o manifesto verdadeiro de instalação v2. Se estiver ausente,
interromper e examinar a instalação existente; não criar um manifesto fictício
nem recompilar automaticamente os executáveis usados no controle.

## Preparar e verificar

O caminho abaixo é o caso original registrado na captura. Se ele foi movido,
ajustar apenas `REFERENCE_CASE` para sua localização real.

```bash
export REFERENCE_CASE=/p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow/experiments/2025-reference/cases/monan-jedi-20250901-7d
export CANDIDATE_CASE="$VALIDATION_WORK/pilot-20250901"
python -m monan_jedi_workflow.scientific_pilot generate "$REFERENCE_CASE" "$CANDIDATE_CASE"
python -m monan_jedi_workflow.scientific_pilot preflight "$CANDIDATE_CASE"
campaign check "$CANDIDATE_CASE/campaign.yaml"
```

A geração recusa destinos existentes e sobrepostos à referência. Não modifica
os originais. Preflight verifica instalação, entradas iniciais, seis IODA,
os dez produtos históricos de comparação e os dois logs JEDI; valida as
sequências de custo e registra hashes em `preflight.json`. As ligações de entrada
da segunda análise apontam para produtos futuros e só serão resolvidas após
MPAS 00Z. Isso é esperado.

## Executar: shell explícito em uma alocação PBS

```bash
cd "$CANDIDATE_CASE"
qsub run-pilot.pbs
```

O shell usa a fila `pesqmidi`, um nó, 128 ranks e até três horas, herdando o
ambiente carregado. Mantém os recursos científicos da referência; a fila/limite
do shell externo deve ser ajustada somente se a política real da JACI exigir.
Chama `check`, `prepare`, `run`, `validate` de cada etapa em sequência e para
no primeiro erro. Não submeter simultaneamente o shell e o workflow exportado.

Alternativa para quem já usa simpleWorkflow:

```bash
campaign export "$CANDIDATE_CASE/campaign.yaml" --engine simpleworkflow
swf validate "$CANDIDATE_CASE/workflow.yaml"
swf plan "$CANDIDATE_CASE/workflow.yaml"
swf run "$CANDIDATE_CASE/workflow.yaml" --ui plain
python -m monan_jedi_workflow.scientific_pilot compare "$CANDIDATE_CASE"
```

A exportação contém nove tarefas: três etapas com prepare/run/validate.
O orquestrador possui as alocações PBS. O shell é uma receita explícita do
usuário, não um novo comando de ciclo completo da plataforma.

## Resultado para devolver

- `pilot.stdout.log` e `pilot.stderr.log` (caminho shell PBS);
- `preflight.json`;
- `comparison.json`;
- em caso de falha, logs JEDI/MPAS da etapa que parou.

`comparison.json` só retorna `passed: true` se os dez produtos tiverem conteúdo
científico exato, as sequências de custo coincidirem e as métricas pareadas de
sondas coincidirem nos dois ciclos. Também compara feedbacks de superfície e
GNSS-RO integralmente, incluindo grupos/QC. Tolerâncias numéricas são zero;
apenas `file_id` da raiz é ignorado. Não relaxar isso automaticamente.
O shell chama a comparação ao terminar. Para repeti-la sem executar o modelo:

```bash
python -m monan_jedi_workflow.scientific_pilot compare "$CANDIDATE_CASE"
```

Aprovação deste piloto comprova somente o replay curto. A etapa seguinte é a
repetição dos sete dias e a avaliação formal M4 do GAD, incluindo reprodução
independente. O−A melhor que O−B mede ajuste às observações assimiladas, não
habilidade independente de previsão.

## Verificações locais desta entrega

231 testes passaram, um teste opcional de simpleWorkflow foi ignorado.
A geração foi exercitada sobre a captura real; os loaders nativos reproduziram
exatamente os 12 templates científicos do piloto. Nessa verificação estática,
a consulta à instalação foi substituída somente dentro do teste local; o código
de geração/preflight entregue não contorna a checagem real. O DAG exportou nove
tarefas e o shell passou em `bash -n`. Nenhuma execução científica ocorreu aqui.
