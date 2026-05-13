# Visão geral do projeto

## O que é

O MONAN-JEDI-WORKFLOW é uma camada de workflow para apoiar experimentos de assimilação de dados usando MONAN/MPAS e JEDI-MPAS. Ele organiza scripts, configurações, validações e templates necessários para preparar e executar experimentos em HPC.

O foco inicial é um experimento **3DVar-FGAT** no JACI, usando PBS e um build externo do MPAS-JEDI.

## Qual problema ele resolve

Sem uma camada de workflow, cada experimento tende a depender de comandos manuais, paths locais, scripts soltos e validações feitas de forma informal. Isso dificulta reprodutibilidade, manutenção e transferência para outras pessoas.

O projeto resolve esse problema criando uma sequência explícita:

```text
configurar ambiente
preparar dados
validar insumos
renderizar YAML JEDI
preparar runtime
gerar PBS
submeter execução
coletar resultados
```

## Para quem foi criado

O projeto foi criado para o contexto MONAN/JEDI no INPE, especialmente para uso no JACI, mas a arquitetura foi pensada para permitir adaptação a outros ambientes HPC.

## Diferenciais

- separação entre configuração científica e configuração de site;
- validações antes de submissão PBS;
- suporte a staging de dados externos;
- inventário IODA;
- checklist científica dos insumos;
- renderização de YAML e PBS;
- preparação para integrar scripts externos do grupo MONAN;
- desenho compatível com futura troca de orquestrador, como Cylc ou ecFlow.

## O que o projeto ainda não é

O projeto ainda não é um sistema operacional completo de previsão. Ele é uma base organizada para chegar a esse ponto de forma segura. A execução científica real depende de:

- build MPAS-JEDI funcional;
- arquivos reais de background;
- observações IODA reais;
- covariância SABER/BUMP compatível;
- validação dos observers JEDI;
- etapa de forecast MONAN/MPAS implementada ou adaptada.
