# Tutorial — do zero a uma campanha MONAN-JEDI

Este é o caminho normal do usuário. Não é necessário procurar outros exemplos.

## 1. Pré-requisitos

Você precisa ter:

- MONAN-JEDI instalado;
- simpleWorkflow instalado;
- este repositório instalado;
- acesso aos dados científicos do experimento.

Selecione o runtime:

```bash
export MONAN_JEDI_INSTALL_ROOT=/caminho/para/monan-jedi
export STACK_ROOT=/caminho/para/spack-stack

monan-jedi-workflow --help
swf --help
```

## 2. Crie a configuração do experimento

Copie o template mantido:

```bash
cp -r examples/case my-experiment
cd my-experiment
```

Você encontrará um único conjunto de arquivos de usuário:

```text
my-experiment/
  campaign.yaml       quando e por quanto tempo executar
  profile.yaml        liga a campanha aos componentes abaixo
  jedi.yaml           análise/DA
  mpas.yaml           forecast MONAN/MPAS
  obs2ioda.yaml       observações
  initialization/     configuração do primeiro estado MPAS
  templates/          namelists, streams e YAML variacional (a preencher)
```

Não crie `workflow.yaml` manualmente. Ele é produto da materialização.

## 3. Configure na ordem correta

### 3.1 Campanha

Abra `campaign.yaml`. Para o primeiro teste escolha uma data para a qual todos
os dados estejam disponíveis e use:

```yaml
duration: P3D
```

Veja [campaign](configuration/campaign.md).

### 3.2 MONAN/MPAS

Abra `mpas.yaml` e confira malha, partição, forecast, intervalo dos estados
DA, namelist/streams e PBS.

Veja [MONAN/MPAS](configuration/mpas.md).

### 3.3 Observações

Abra `obs2ioda.yaml`. Para cada observação confirme origem, conversor e output
IODA. A lista `converters[*].outputs` é a lista de produtos que a campanha
espera.

Veja [observações](configuration/observations.md).

### 3.4 JEDI

Abra `jedi.yaml` e confira ciclo/janela, background, B, links das observações,
YAML variacional, recursos PBS e validação.

Depois confira o YAML variacional em `templates/`: geometry, variáveis,
B, observers, operadores, QC, erros e minimização.

Veja [JEDI](configuration/jedi.md).

## 4. Verifique antes de executar

Da raiz do repositório:

```bash
monan-jedi-workflow campaign check my-experiment/campaign.yaml
```

Corrija tudo que aparecer como erro. Não prossiga enquanto o preflight não
estiver limpo.

## 5. Materialize sem submeter

```bash
monan-jedi-workflow campaign create my-experiment/campaign.yaml
```

O diretório indicado por `campaign.destination` será criado. Agora sim ele
conterá o `workflow.yaml`.

Inspecione:

```bash
swf plan CAMPAIGN_DESTINATION/workflow.yaml
```

Até aqui nenhum experimento científico deve ter sido submetido.

## 6. Execute

```bash
monan-jedi-workflow campaign run my-experiment/campaign.yaml
```

Acompanhe:

```bash
monan-jedi-workflow campaign status my-experiment/campaign.yaml
```

## 7. Valide três dias

Antes de ampliar o período, confirme:

- todos os ciclos terminaram;
- observações foram convertidas e usadas;
- JEDI terminou com seus marcadores de sucesso;
- análises foram produzidas;
- forecasts MPAS terminaram;
- cada forecast forneceu o estado esperado ao ciclo seguinte;
- horários NetCDF são coerentes;
- logs não mostram erro científico silencioso.

## 8. Amplie sem mudar a ciência

Crie uma nova campanha/destination e altere apenas a duração:

```text
P3D -> P7D -> P30D -> P365D
```

Se for necessário alterar Python apenas porque a duração aumentou, isso deve
ser tratado como defeito do workflow, não como procedimento do usuário.

## Próximo marco

O template `examples/case` será fechado com o baseline científico 2025 antes
de ser declarado pronto para produção. Até lá, nenhum valor científico de
exemplo deve ser interpretado como recomendação universal.


## O que NÃO usar

Não há um segundo diretório de exemplos para escolher. O caminho mantido é
`examples/case/`. Material de reprodução histórica foi retirado da árvore
ativa e permanece preservado em `archive/pre-cleanup-2026-10-01`.

Os comandos de stage (`jedi-prepare`, `mpas-prepare`, `obs2ioda-run` etc.)
são usados pelo workflow e servem para diagnóstico/desenvolvimento. Para uma
campanha normal, use a interface `campaign`.
