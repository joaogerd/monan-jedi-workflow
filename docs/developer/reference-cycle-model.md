# Modelo conceitual de referência para Cycling DA

## Objetivo

Registrar o que é estruturalmente necessário para rodar uma campanha cíclica sem transformar um tutorial antigo em dependência da implementação atual.

## Sequência conceitual

```text
observations for t
       |
       v
Obs2IODA / validated IODA
       |
       +------------------+
                          |
background for t ---------+--> MPAS-JEDI analysis(t)
                                |
                                v
                           analysis(t)
                                |
                                v
                           MPAS forecast
                                |
                                v
                     background for t + step
```

A matriz B é um artefato previamente construído e validado que entra no estágio de análise.

## Artefatos necessários

A implementação atual deve conseguir identificar explicitamente:

- executável JEDI;
- executável MPAS;
- background;
- análise;
- observações IODA;
- matriz B;
- mesh/invariant/static assets;
- graph partition compatível com a decomposição MPI;
- namelist/streams e arquivos relativos necessários;
- logs;
- outputs usados para comprovar sucesso.

## O que é invariável e o que é versionado

### Conceitualmente estável

- observações precisam estar disponíveis antes da análise;
- análise consome background + observações + B + geometria;
- forecast é inicializado por um estado de análise;
- um produto do forecast alimenta o ciclo seguinte;
- cada fronteira deve possuir entradas/saídas verificáveis.

### Dependente da versão/configuração

- nome do executável;
- chaves do YAML;
- variáveis do estado;
- streams;
- nomes dos HDF5/IODA;
- convenção exata do output da análise;
- quantidade de ranks e arquivo `graph.info.part.*`;
- estrutura interna da B.

## Uso do tutorial histórico

O tutorial “Cycling DA with MPAS-A and MPAS-JEDI” do repositório GAD-DIMNT-CPTEC/JEDI é uma referência para a intenção do workflow e para o inventário conceitual. Ele foi feito para uma versão anterior e não deve ser tratado como receita literal para o código atual.

Toda adaptação deve responder duas perguntas:

1. qual era a função científica/operacional desta etapa no tutorial?;
2. qual é a forma correta de cumprir essa função no baseline atual?
