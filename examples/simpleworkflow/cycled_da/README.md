# Cycling DA de referência com simpleWorkflow

Este diretório descreve a **DAG de pesquisa**, não um pacote de dados científicos pronto. O objetivo é tornar explícita e pequena a tradução:

```text
Obs2IODA -> JEDI FGAT trajectory/analysis -> MPAS forecast -> next cycle
```

Os mesmos comandos de domínio podem ser chamados futuramente por ecFlow ou Cylc.

## Arquivos

```text
workflow.yaml.example  DAG, período e contratos de artefatos
obs2ioda.yaml.example  PREPBUFR -> IODA em layout previsível
jedi.yaml.example      contrato cycle-aware da análise
mpas.yaml.example      handoff análise -> forecast/background
templates/             YAML JEDI derivado do baseline que passou
```

## Criar um caso

```bash
mkdir -p cases/3dfgat_x1.10242
for name in workflow obs2ioda jedi mpas; do
  cp "examples/simpleworkflow/cycled_da/${name}.yaml.example" \
     "cases/3dfgat_x1.10242/${name}.yaml"
done
cp -a examples/simpleworkflow/cycled_da/templates \
  cases/3dfgat_x1.10242/
```

Edite os caminhos marcados nos arquivos de domínio. O wrapper PREPBUFR continua sendo o wrapper compartilhado em `scripts/obs2ioda/`; ele não é duplicado aqui.

O template variacional preserva os três observers do `baseline_passed.yaml`: Radiosonde, GnssroRefNCEP e SfcCorrected. O PREPBUFR convencional fornece Radiosonde/superfície; portanto o exemplo declara o IODA GNSSRO como entrada externa por ciclo. Isso é deliberado: não removemos ciência do baseline só para fazer o exemplo parecer autocontido.

Para x1.10242, o template materializa `config_dt=1200 s` e usa
`model.tstep=PT20M`. O preflight exige igualdade porque a implementação
MPAS-JEDI auditada executa um timestep físico por `OOPS Model::step`.

## Preflight

```bash
monan-jedi-workflow cycle-doctor cases/3dfgat_x1.10242 \
  --cycle 2018-04-15T00:00:00Z
```

## Um ciclo

```bash
swf plan cases/3dfgat_x1.10242/workflow.yaml
swf run cases/3dfgat_x1.10242/workflow.yaml \
  --cycle-time 2018-04-15T00:00:00Z
```

## Dois ciclos

```bash
swf run cases/3dfgat_x1.10242/workflow.yaml \
  --from 2018-04-15T00:00:00Z \
  --to   2018-04-15T06:00:00Z \
  --step PT6H
```

Valide o handoff entre os dois ciclos antes de ampliar o período.

## Restart

A DAG declara manifests e produtos científicos essenciais como artifacts do `simpleWorkflow`. Assim, um sucesso anterior só é reutilizado quando os outputs declarados continuam presentes.

Isso complementa — não substitui — os manifests internos dos stages em `.monan-jedi-workflow/`.

## O que ainda exige validação no JACI

Antes da primeira submissão real, confirme com o baseline atual:

- se `baseline_passed.yaml` ainda representa a compilação atual;
- nomes de análise e forecast;
- duração necessária do MPAS para materializar o background FGAT;
- success markers dos logs;
- disponibilidade das observações de cada ciclo (inclusive GNSSRO);
- caminhos/forma de consumo da B;
- mesh/static e partição MPI.
