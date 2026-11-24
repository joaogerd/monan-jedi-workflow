# MONAN-JEDI Workflow

Plataforma para criar, executar e diagnosticar experimentos de assimilação de dados com **MPAS-JEDI**, com orquestração por **simpleWorkflow** na JACI. O nome MONAN-JEDI identifica o projeto; a receita de referência atual ainda usa o núcleo MPAS, e a integração com o núcleo MONAN exige validação própria.

> **Versão beta:** `0.3.0b1`. A receita científica atualmente validada na JACI é MPAS-JEDI 3DVar/FGAT (240 km, 55 níveis); outros perfis requerem validação própria.

## Por onde começar

**[Tutorial oficial — instalação, primeiro experimento, execução e diagnóstico](docs/tutorial.md)** é a referência de uso. Ele explica o significado de cada diretório, os comandos, as entradas, os produtos, como identificar problemas e como não perder uma execução.

Para consultas específicas:

- [Configuração da campanha](docs/configuration/campaign.md): sintaxe **atual** de `campaign.yaml`, datas inclusivas/exclusivas e exportação.
- [Diagnóstico de falhas](docs/diagnostics.md): `diagnose`, causa raiz, logs, PBS e limites da retomada.
- [Figuras científicas](docs/scientific-plots.md): `experiment plots`, O−B/O−A, custos variacionais, continuidade e exportação PNG/PDF/SVG.
- [Referência arquitetural para desenvolvedores](docs/developer/architecture.md): fronteiras entre aplicativos, orquestrador e execução científica.
- [Contribuição ao projeto](CONTRIBUTING.md): testes, mudanças e revisão.
- [Registros de decisões](docs/developer/adr/README.md) e [evidências de validação](docs/validation/): histórico técnico, **não** instruções alternativas de execução.
- [Auditoria da documentação](docs/DOCUMENTATION_AUDIT.md): decisões de limpeza, incompatibilidades removidas e portões antes do merge.

## Instalação

Requer Python 3.10 ou superior. A instalação do pacote **não compila nem instala** MPAS, MPAS-JEDI, WPS, conversores Obs2IODA ou o stack científico da JACI.

```bash
git clone --branch feat/platform-domain-apps \
  https://github.com/joaogerd/monan-jedi-workflow.git
cd monan-jedi-workflow
python -m pip install -e '.[dev,orchestration]'
experiment --help
diagnose --help
swf --help
```

A instalação acima é apropriada ao **desenvolvimento**. Antes de uma campanha científica, fixe as versões do checkout e do ambiente e siga o tutorial para configurar um workspace e os recursos científicos existentes. **Não atualize o pacote nem os executáveis durante uma campanha.**

## Como os componentes se relacionam

```text
experiment create -> campaign.yaml + configurações científicas
         |
         v
experiment check -> experiment export -> workflow.yaml
         |
         v
experiment validate -> experiment plan -> experiment run
                                             |
                                      simpleWorkflow (login)
                                             |
                         +-------------------+-------------------+
                         |                                       |
                 WPS/MPAS inicialização                  Ciclos de 6 h
                                                      Obs2IODA -> JEDI -> MPAS
                         |                                       |
                         +-------------- PBS nativo ------------+
```

O controlador Python roda no nó de login, de onde os aplicativos submetem e acompanham **jobs PBS nativos** quando necessário. Os nós de computação executam programas e scripts científicos, não o controlador Python.

Os comandos públicos do fluxo novo são `experiment create/check/export/validate/plan/run/status` e `diagnose`. Os aplicativos `obs`, `jedi`, `mpas`, `wps`, `diagnostic(s)` e `campaign` permanecem acessíveis para operações de domínio ou compatibilidade. Não comece pela antiga interface `monan-jedi-workflow campaign create/run`.

## Primeiro experimento científico

O destino deve ser novo. **Substitua os exemplos pelos caminhos autorizados da sua conta** e garanta que o workspace tenha um perfil de site verificado, como explica o tutorial.

```bash
export WORKSPACE=/p/projetos/SEU_GRUPO/SEU_USUARIO/monan-jedi
export CASE="$WORKSPACE/experiments/primeiro-experimento"
mkdir -p "$WORKSPACE/experiments"

experiment create "$CASE" --workspace "$WORKSPACE" \
  --start 2026-01-30T00:00:00Z

cd "$CASE"
source ./environment.sh
experiment check-inputs .
experiment check campaign.yaml
experiment export campaign.yaml
experiment validate workflow.yaml
experiment plan workflow.yaml
# Apenas após conferir dados científicos e recursos PBS:
experiment run workflow.yaml --ui plain
```

O `experiment check-inputs .` verifica o GFS inicial e as observações **de todos os ciclos declarados**, incluindo campanhas de sete dias. Isso não verifica isoladamente executáveis, disponibilidade PBS nem a qualidade científica. O teste artificial em `examples/beta` verifica somente contratos de software.

## Quando ocorrer uma falha

No diretório do experimento:

```bash
diagnose . --no-pbs     # somente logs locais, sem contato com PBS
diagnose .              # inclui consulta ao PBS quando disponível
```

O diagnóstico é somente leitura. **Não apague** `.simpleworkflow/`, manifests ou produtos científicos para forçar uma reexecução. O estado `SUCCESS` sozinho não prova que uma retomada manterá a mesma assinatura dos executáveis e do ambiente.

## Critérios para a integração

**Evidência obtida:** campanha independente de sete dias na JACI (30/01–06/02/2026), com 29 análises, 28 previsões entre ciclos, 267 tarefas concluídas e diagnósticos de convergência/consistência observacional. [Relatório institucional M3/M4](https://github.com/GAD-DIMNT-CPTEC/monan-jedi-2026/blob/main/docs/relatorios/M3_7dias_2026-01.md).

**Ainda fora desse escopo:** generalização científica para outras resoluções, warm start, retomada após falhas arbitrárias e verificação independente da previsão. A integração de branches exige testes automáticos e conferência dos comandos de instalação e documentação no commit integrado.
