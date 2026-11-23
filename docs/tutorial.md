# Tutorial — primeiro experimento MONAN-JEDI e campanhas na JACI

> **Escopo:** branch `feat/platform-domain-apps`, pacote beta `0.3.0b1`. Este é o caminho de entrada para **usuários novos**, a partir da instalação. A implementação atual da receita científica usa **MPAS-JEDI** com 3DVar/FGAT; o nome da plataforma MONAN-JEDI **não** significa que o executável do núcleo MONAN já esteja sendo usado. Não confundir com a interface antiga `monan-jedi-workflow campaign create/run`.
>
> **Estado da validação:** já foi demonstrado um caso científico de duas análises consecutivas (00Z e 06Z, 30/01/2026) na JACI. As campanhas independentes de 3 e 7 dias do branch refatorado estão sob avaliação; sucesso de tarefas não equivale, por si só, à homologação científica. As campanhas históricas de 2018 e 2025 pertencem a outros estados do software.

## 1. Entender a sequência antes de instalar

O usuário cria um **experimento** (receita científica, ambiente, arquivos de configuração) e uma **campanha** (datas e operações). O `experiment export` converte a campanha em `workflow.yaml`; `experiment run` delega a execução ao `simpleWorkflow`.

```text
NÓ DE LOGIN (controlador Python; simpleWorkflow)
  experiment create
       |
       v
  environment.sh + science/*.yaml + campaign.yaml
       |
       v
  experiment check -> experiment export -> experiment validate -> experiment plan
       |
       v
  experiment run (simpleWorkflow, tarefas locais de controle)
       |
       +-- Inicialização, uma vez:
       |     WPS prepare -> WPS run/validate -> MPAS Init -> MPAS 6 h
       |
       +-- Para cada análise de 6 h:
             OBS convert -> JEDI (análise) -> MPAS (previsão 6 h)
                    ^                          |
                    +----- background seguinte-+
```

Cada etapa de controle tem `prepare`, `run` e `validate`. Quando a ciência exige recursos da JACI, o aplicativo submete um **script PBS nativo** via `qsub` e acompanha o job. **Não se executa Python/Conda do workflow nos nós de computação.** O Conda do controlador pode residir no diretório pessoal, mas entradas, executáveis, bibliotecas e produtos científicos devem ser acessíveis aos compute nodes.

As interfaces independentes continuam disponíveis: `obs acquire`, `obs convert`, `jedi`, `mpas init`, `mpas`, `diagnostics`, `campaign`, `wps` e `diagnose`. O primeiro experimento não exige chamar cada aplicativo manualmente.

## 2. Instalar uma única vez

**Pré-requisitos:** Python >= 3.10; acesso à JACI, ambiente PBS e instalação científica de WPS, MPAS/MPAS-JEDI e Obs2IODA; malha, tabelas de física e matriz B adequadas ao caso. Instalar o pacote Python **não** instala ou compila os modelos científicos.

```bash
git clone --branch feat/platform-domain-apps \
  https://github.com/joaogerd/monan-jedi-workflow.git

cd monan-jedi-workflow
python -m pip install -e '.[dev,orchestration]'

experiment --help
campaign --help
swf --help
diagnose --help
```

O `simpleWorkflow` é dependência do pacote, atualmente fixada num commit em `pyproject.toml`. Instalação editável é útil no desenvolvimento, **não** autoriza atualizar o checkout enquanto uma campanha está executando. Fixe o commit antes do experimento e registre `git rev-parse HEAD`.

### 2.1. Alternativa: testar sem dados científicos (opcional)

Este teste artificial verifica apenas contratos de entrada e saída dos aplicativos. Não use os produtos como evidência meteorológica.

```bash
# A partir da raiz do checkout:
mkdir -p /p/projetos/SEU_GRUPO/SEU_USUARIO/testes
cp -r examples/beta /p/projetos/SEU_GRUPO/SEU_USUARIO/testes/beta-ciclo
cd /p/projetos/SEU_GRUPO/SEU_USUARIO/testes/beta-ciclo
bash manual.sh experiment.yaml 2025-09-01T00:00:00Z
```

O script registra `manual-test.log` e só imprime `TODOS OS 5 TESTES PASSARAM` se os cinco aplicativos artificiais passarem em `prepare/run/validate/status`. Não reaproveite esse diretório para ciência.

## 3. Preparar um workspace científico

Os exemplos a seguir são **variáveis a configurar no seu ambiente**, não caminhos obrigatórios do software:

```bash
# Edite conforme seu grupo e usuário; diretórios em /p são exemplos JACI.
export WORKSPACE=/p/projetos/SEU_GRUPO/SEU_USUARIO/monan-jedi
export CASE="$WORKSPACE/experiments/primeiro-experimento"

mkdir -p "$WORKSPACE/experiments"
```

O workspace precisa dispor do `site.yaml` validado com o ambiente científico e as variáveis que apontam para os recursos compartilhados. No onboarding já configurado, `experiment create --workspace` reutiliza esse perfil. Em uma instalação sem perfil, consulte `experiment site init --help` e valide o `site.yaml` gerado **antes de criar o caso**. Consulte também [primeiro experimento na JACI](first-experiment.md) e [configuração do ambiente](configuration/campaign.md).

A receita científica de referência utiliza resolução, malha, partição e parâmetros declarados nos YAML gerados. Eles são **exemplos específicos da receita**, não valores embutidos que devam ser copiados para outras resoluções.

## 4. Criar o primeiro experimento científico — dois ciclos

Escolha uma data realmente coberta por observações e pelo GFS de inicialização. A data abaixo é a do caso que serviu aos testes operacionais; **não é um default obrigatório**.

```bash
experiment create "$CASE" \
  --workspace "$WORKSPACE" \
  --start 2026-01-30T00:00:00Z

cd "$CASE"
source ./environment.sh
```

O destino deve ser **novo**. O criador recusa sobrescrever um diretório existente. Por padrão, usa `cold start`; `warm start` científico não está implementado.

Arquivos principais:

| Arquivo/diretório | Para que serve |
| --- | --- |
| `environment.sh` | carrega e verifica as variáveis do caso |
| `science/` | configurações específicas de WPS, MPAS, JEDI, Obs2IODA, templates e perfil |
| `experiment.yaml` | aponta para as configurações científicas dos ciclos |
| `init.yaml` / `initialization.yaml` | inicialização WPS/MPAS anterior à primeira análise |
| `campaign.yaml` | declara calendário, operações e `workflow.yaml` de saída |
| `work/` | produtos científicos, manifests e logs, após execução |
| `.simpleworkflow/` | histórico e estado do orquestrador, após execução |

`experiment create` gera configurações e links de background, **não submete jobs nem produz análises**. Na receita de referência, a primeira análise ocorre às 00Z, a segunda às 06Z e a inicialização às 18Z do dia anterior.

## 5. Verificar os dados antes de gastar horas de JACI

```bash
cd "$CASE"
source ./environment.sh

# Este comando da versão atual verifica o GFS inicial
# e as observações dos DOIS ciclos da receita curta.
experiment check-inputs .

experiment check campaign.yaml
experiment export campaign.yaml
experiment validate workflow.yaml
experiment plan workflow.yaml

# Inspeção do plano: não executa tarefas científicas.
swf run workflow.yaml --dry-run --ui plain
```

**Verifique também:** disponibilidade real da malha/partições, física, matriz B, executáveis, bibliotecas do stack, permissões de escrita e limites das filas PBS. `source environment.sh` prova que os diretórios básicos existem, não que todos os arquivos científicos estão corretos.

O GFS pode ser **obtido automaticamente** por `wps prepare` quando a receita declara `wps.acquisition` com um provedor HTTPS válido e cache gravável. A opção habilitada, sozinha, **não garante** que a URL exista ou que o download funcione. PREPBUFR/GNSS-RO também precisam de entradas datadas válidas. Nunca reutilize silenciosamente dados de outro horário.

## 6. Executar, acompanhar e verificar o primeiro experimento

Somente após aprovar as verificações:

```bash
cd "$CASE"
source ./environment.sh
set -o pipefail

experiment run workflow.yaml --ui plain 2>&1 | tee run.log
experiment status workflow.yaml
```

A receita curta tem **9 tarefas de inicialização e 15 tarefas cíclicas**: OBS/JEDI/MPAS no primeiro ciclo, OBS/JEDI no segundo. Resultado esperado: **duas análises JEDI e uma previsão MPAS entre elas**, além da previsão de inicialização. A validação deve confirmar produtos NetCDF, horários, observações e convergência — não apenas a palavra `SUCCESS` no orquestrador.

Durante a campanha, use outro terminal com `qstat -u "$USER"`; não lance outro `run` enquanto o controlador estiver ativo.

## 7. Se falhar: um comando de diagnóstico

```bash
cd "$CASE"
diagnose . --no-pbs
```

O comando **não altera arquivos nem ressubmete jobs**. Ele mostra a tarefa de origem do erro e o `stderr` relevante, em vez de listar centenas de dependentes `BLOCKED`.

Para detalhes:

```bash
diagnose . --verbose
diagnose . --json
swf explain workflow.yaml
```

Para consultar o PBS use `diagnose .` (sem `--no-pbs`). `swf explain --task` tem uma limitação na versão atual: selecionar uma tarefa de inicialização pode produzir `Unknown selected task(s)` ao tentar usar a seleção também na fase cíclica. Use `swf explain workflow.yaml` sem `--task` até a correção.

**Regra para retomada:** nunca apague `.simpleworkflow/`, manifests, scripts PBS ou produtos validados apenas para forçar nova execução. Não use `--force` ou `reset` e **não reinstale** o pacote durante a campanha. As assinaturas do `simpleWorkflow` incluem metadados do executável e hashes do ambiente (`PATH`, `PYTHONPATH` etc.); mudar o controlador pode provocar uma tentativa indevida de repetir tarefas científicas. `status SUCCESS` e `explain SUCCESS` não substituem a comparação das assinaturas. Ver [guia de diagnóstico](diagnostics.md).

### Caso real: observações do quinto ciclo

Na campanha de sete dias iniciada em 30/01/2026, a inicialização e quatro ciclos 00/06/12/18Z foram concluídos, mas `c00004_obs_convert_prepare` falhou. O erro era **do resolvedor de caminhos**: interpretava a data `20260130` do diretório `m3-7dias-20260130` como data do PREPBUFR e chegava a tentar mudar o diretório do script `run_prepbufr.sh`. Os arquivos reais de 31/01 00Z existiam.

A correção restringiu a interpretação temporal ao **nome do arquivo observacional** e excluiu scripts da verificação. O diagnóstico agora mostra essa causa diretamente. O teste da correção e a retomada segura da campanha longa na JACI são verificações distintas; não declarar os 29 ciclos concluídos antes dos respectivos resultados.

## 8. Campanhas longas: 3 e 7 dias (avançado)

A interface `experiment create` da beta **cria somente dois ciclos e seus backgrounds**. **Não basta editar o `calendar.end`**: para uma execução longa também devem existir os vínculos de trajetória/estado para cada análise adicional. Há um preparador **específico da receita MPAS atual** no [repositório institucional](https://github.com/GAD-DIMNT-CPTEC/monan-jedi-2026/tree/main/experiments/M3/platform-domain-apps), que estende o calendário e cria links para os backgrounds futuros **em um experimento novo, ainda não exportado**. Ele não é um recurso genérico da API nem foi projetado para modificar uma campanha em andamento.

Exemplo de planejamento para 30/01/2026 00Z, horário final **inclusivo**:

| Período | Final UTC inclusivo | Análises | Previsões MPAS entre ciclos |
| --- | --- | ---: | ---: |
| 3 dias (72 h) | 02/02/2026 00Z | 13 | 12 |
| 7 dias (168 h) | 06/02/2026 00Z | 29 | 28 |

Cada campanha precisa de diretório, `campaign.yaml`, `workflow.yaml` e `.simpleworkflow/` **independentes**; não aumente a duração de um experimento já executado. O preparador verifica PREPBUFR/GNSS-RO de todos os horários, mas isso não substitui o preflight integral de GFS, recursos científicos e scheduler. **`experiment check-inputs .` continua limitado aos primeiros dois ciclos.**

Passo a passo específico, com comandos completos e condições de segurança: [campanhas M3 de 3/7 dias na JACI](https://github.com/GAD-DIMNT-CPTEC/monan-jedi-2026/blob/main/experiments/M3/platform-domain-apps/README.md).

O formato genérico `campaign.yaml` também permite definir `calendar.end` e `end_inclusive`. Use **final inclusivo** se quiser a análise às 00Z do último dia (13 ou 29 análises); use **final exclusivo** para 12 ou 28 análises, respectivamente. Essas convenções produzem contagens diferentes e não devem ser confundidas na comparação de campanhas.

Não iniciar 7 dias antes de avaliar a campanha de 3 dias; não iniciar 30 dias/1 ano antes de demonstrar estabilidade, controle de armazenamento, assinaturas e estratégia de restart em horizontes menores. O grafo estático cresce com o período e precisa de testes de escalabilidade para campanhas anuais.

## 9. Critérios de validação científica e documentação

Para cada ciclo, preservar: timestamp e estado da tarefa, ID PBS e logs nativos, validação IODA, análise JEDI, valores de função custo por iteração, O-B/O-A e QC quando disponíveis, estado completo e tempo dos outputs MPAS, continuidade do background, versão Git, YAML efetivamente usados e identificadores digitais (hashes).

Critérios para relatórios longos: quantidade de análises e previsões esperadas, ausência de lacunas, porcentagem de ciclos aceitos, convergência, integridade/tempos NetCDF, O-B/O-A por variável/observador, comportamento temporal e registros de restart. Resultados de O-A próximos das observações assimiladas são **consistência do ajuste**, não validação independente de previsão.

Relatórios históricos e a validação pós-refatoração estão organizados no [projeto institucional](https://github.com/GAD-DIMNT-CPTEC/monan-jedi-2026). Uma nova execução só será considerada concluída quando seus próprios logs, métricas e relatórios estiverem disponíveis.

## 10. Referências e restrições da beta

- [Primeiro experimento científico na JACI](first-experiment.md) — detalhes de inicialização, PBS nativo e migração de casos antigos.
- [Diagnóstico de erros](diagnostics.md) — informações adicionais e JSON.
- [Configuração de campanhas](configuration/campaign.md) — semântica de calendários e configurações.
- [Testes beta](beta-testing.md) — fixture artificial e validação de contratos.
- [Campanhas M3 de 3/7 dias](https://github.com/GAD-DIMNT-CPTEC/monan-jedi-2026/tree/main/experiments/M3/platform-domain-apps) — preparador externo específico da receita.

Antes de promover esta versão a release estável ainda é necessário: consolidar onboarding sem paths pessoais como dependência, testar instalação fora do checkout, validar generalidade das resoluções/meshes, garantir diagnósticos e retomada segura no `simpleWorkflow`, fixar revisões científicas e publicar os resultados das campanhas prolongadas.
