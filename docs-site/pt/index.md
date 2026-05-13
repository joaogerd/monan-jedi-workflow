# MONAN-JEDI-WORKFLOW

O **MONAN-JEDI-WORKFLOW** é um projeto para organizar, validar e executar experimentos de assimilação de dados com **MONAN/MPAS-JEDI** em ambientes HPC do INPE, com foco inicial no supercomputador **JACI** e em ciclos **3DVar-FGAT**.

A proposta não é criar um bloco monolítico. O projeto separa claramente ambiente, dados, configuração científica, execução, validação e orquestração.

## O que o projeto resolve

O projeto cria uma camada operacional reprodutível para:

- preparar o ambiente do JACI;
- organizar dados externos de entrada;
- validar arquivos científicos antes da submissão;
- renderizar configurações JEDI;
- preparar diretórios de runtime;
- gerar jobs PBS;
- apoiar a futura ciclagem de assimilação e previsão.

## Público-alvo

- pesquisadores de assimilação de dados;
- desenvolvedores MONAN/JEDI;
- usuários HPC no INPE;
- equipes que precisam testar ciclos de assimilação de forma rastreável;
- futuros operadores ou mantenedores do workflow.

## Estado atual

A base atual suporta a preparação estrutural de um primeiro caso **3DVar-FGAT**. O fluxo ainda depende da disponibilização dos arquivos científicos reais e do build MPAS-JEDI no JACI.

## Leitura recomendada

1. [Visão geral](overview.md)
2. [Arquitetura](architecture.md)
3. [Instalação e configuração](installation.md)
4. [Guia de uso](usage.md)
5. [Cookbook / How-to](cookbook.md)
