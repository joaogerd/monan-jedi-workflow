# MONAN-JEDI Workflow

Plataforma de execução de experimentos MONAN/MPAS + JEDI, integrada ao **simpleWorkflow**.

> **Branch candidata à primeira release:** `feat/platform-domain-apps` — beta `0.3.0b1`. A execução científica na JACI e as campanhas longas ainda precisam de homologação; exemplos `examples/beta` usam produtos artificiais.

## Comece aqui

1. **[Tutorial operacional — 1 ciclo, 1 dia e campanhas de 3/7/30/365 dias](docs/tutorial.md)** — caminho recomendado para novos usuários.
2. [Referência da beta, comandos dos aplicativos e suas limitações](docs/beta-testing.md).
3. [Solução de problemas e retomada](docs/troubleshooting.md) — observar que partes da documentação legada ainda serão consolidadas.

## Aplicativos

| Comando | Responsabilidade |
| --- | --- |
| `obs acquire` / `obs convert` | Aquisição de observações e conversão IODA |
| `jedi` | Assimilação e produção da análise |
| `mpas init` / `mpas` | Inicialização opcional e previsão |
| `diagnostics` | Validação e diagnósticos |
| `campaign` | Verificação e exportação do grafo para simpleWorkflow |

O app `campaign` **não submete nem executa tarefas**; o simpleWorkflow é o executor. Cada operação de domínio segue `inspect/check/prepare/run/validate/status` (conforme o comando). O app `campaign` oferece `inspect/check/export`.

## Instalação da branch candidata

```bash
git clone --branch feat/platform-domain-apps https://github.com/joaogerd/monan-jedi-workflow.git
cd monan-jedi-workflow
python -m pip install -e '.[dev,orchestration]'
campaign --help
swf --help
```

Python >=3.10. A instalação do pacote **não** compila MPAS/MONAN, MPAS-JEDI ou Obs2IODA. Para uma campanha real é indispensável o runtime científico instalado e a receita validada do grupo.

## Execução pelo caminho novo

O **simpleWorkflow roda somente os aplicativos Python no login**. Cada app
prepara sua operação, submete o script PBS nativo pelo `qsub` quando necessário,
aguarda o job e valida os resultados. **Nenhuma CLI Python é executada no
compute node.** O Conda pode permanecer em `$HOME`.

Para criar o primeiro caso científico de referência:

```bash
export NEW_CASE=/p/projetos/monan_das/$USER/work/first-experiment-20250901-login
python -m monan_jedi_workflow.experiment_start "$NEW_CASE"
cd "$NEW_CASE"
source ./environment.sh
campaign check campaign.yaml
campaign export campaign.yaml --engine simpleworkflow
swf validate workflow.yaml
swf plan workflow.yaml
```

Para um caso **já exportado na arquitetura antiga**, siga
[Atualização segura do primeiro experimento](docs/first-experiment.md) e use
`--upgrade-existing` para criar `campaign-login.yaml` e
`workflow-login.yaml` sem substituir os arquivos anteriores.

Só execute `swf run` após verificar entradas científicas, ambiente de módulos,
programas, recursos, tempos e scripts PBS. O `simpleWorkflow` tem executor
PBS próprio para outros usos, mas **não é empregado nesta integração**:
seus tasks ficam todos como `executor: local`; a submissão científica
pertence aos aplicativos MONAN-JEDI.

## Identificar falhas sem analisar logs manualmente

Se uma execução parar, entre no diretório do experimento e use:

```bash
monan-jedi-workflow diagnose
```

O diagnóstico consulta o PBS, lê os relatórios das operações e agrupa
mensagens repetidas de MPI para exibir uma causa provável e orientar a
correção. O comando **não altera arquivos nem ressubmete jobs**.
Veja o [guia de diagnóstico](docs/diagnostics.md) para uso e exemplos.

## Critérios para release estável

Validar um ciclo científico real, um dia completo e depois 3, 7 e 30 dias, com inspeção de produtos, dependências entre ciclos, restart e recursos na JACI. Somente depois iniciar a operação anual. A duração não pode exigir alterações no código nem em escolhas científicas.

As interfaces legadas `monan-jedi-workflow campaign create/run` permanecem disponíveis durante a transição, mas **não** são o caminho recomendado para novos usuários desta branch.
