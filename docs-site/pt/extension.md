# Adaptação e extensão do sistema

## O que pode ser adaptado

O projeto foi desenhado para permitir adaptação controlada de:

- ambientes HPC diferentes do JACI;
- filas e contas PBS;
- caminhos de dados e builds;
- novos experimentos;
- novos observers JEDI;
- novos scripts de forecast MONAN/MPAS;
- futura orquestração com Cylc ou ecFlow.

## O que deve permanecer estável

As interfaces entre camadas devem permanecer estáveis:

- `configs/sites/` define ambiente e paths;
- `configs/experiments/` define escolhas do experimento;
- `scripts/setup/` prepara e valida;
- `scripts/run/` executa etapas de alto nível;
- `tools/` concentra lógica reutilizável;
- `jobs/` contém templates de submissão.

## Reutilização

Para reutilizar o sistema em outro experimento, crie um novo diretório em `configs/experiments/` e reaproveite os validadores já existentes sempre que possível.

## Boas práticas

- não colocar paths absolutos dentro de templates científicos;
- não acoplar lógica científica ao PBS;
- não esconder comandos críticos dentro de arquivos de orquestração;
- manter exemplos versionados e arquivos reais fora do Git;
- documentar toda decisão que afete operação ou ciência.

## Limites atuais

O workflow ainda não implementa completamente:

- execução real do forecast MONAN/MPAS;
- ciclagem semanal automática;
- validação interna de NetCDF/HDF5;
- observers JEDI cientificamente validados;
- camada ecFlow.

Esses pontos devem ser tratados como extensões futuras, sem quebrar a separação de responsabilidades já criada.
