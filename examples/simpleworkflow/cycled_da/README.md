# Cycling DA de referência com simpleWorkflow

Este diretório descreve a **DAG de pesquisa**, não um pacote de dados científicos pronto. O objetivo é tornar explícita e pequena a tradução:

```text
Obs2IODA -> JEDI analysis -> MPAS forecast -> next cycle
```

Os mesmos comandos de domínio podem ser chamados futuramente por ecFlow ou Cylc.

## Arquivos

```text
workflow.yaml.example  DAG e período
jedi.yaml.example      contrato cycle-aware da análise
mpas.yaml.example      handoff análise -> forecast/background
```

Para observações, reutilize um perfil em `examples/obs2ioda/` e copie-o para o caso como `obs2ioda.yaml`.

## Criar um caso

```bash
mkdir -p cases/3dfgat_x1.10242
cp examples/simpleworkflow/cycled_da/workflow.yaml.example \
   cases/3dfgat_x1.10242/workflow.yaml
cp examples/simpleworkflow/cycled_da/jedi.yaml.example \
   cases/3dfgat_x1.10242/jedi.yaml
cp examples/simpleworkflow/cycled_da/mpas.yaml.example \
   cases/3dfgat_x1.10242/mpas.yaml
cp examples/obs2ioda/prepbufr-tutorial/obs2ioda.yaml.example \
   cases/3dfgat_x1.10242/obs2ioda.yaml
```

Edite os caminhos marcados nos três arquivos de domínio.

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

## O que ainda exige validação no JACI

Os templates não afirmam compatibilidade automática com uma compilação do MONAN-JEDI. Antes da primeira submissão real, confirme com o baseline atual:

- YAML JEDI real usado como template;
- nomes de análise e forecast;
- duração necessária do MPAS para materializar o background FGAT;
- success markers dos logs;
- observações habilitadas;
- caminhos da B;
- mesh/static e partição MPI.
