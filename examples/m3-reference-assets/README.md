# Arquivos pequenos da referência M3 executada

Captura recebida da JACI em 12/10/2026. Todos os 5541 checksums do pacote original
foram conferidos. Este diretório seleciona somente os 12 arquivos necessários
ao runtime JEDI da referência histórica de três dias; não inclui dados de 2018.

`provenance.json` registra os caminhos originais e o SHA-256 de cada arquivo.
Os arquivos deste diretório estão preservados byte a byte. Alterações futuras
devem ser explícitas e acompanhadas de nova proveniência.

Referência institucional: `GAD-DIMNT-CPTEC/monan-jedi-2026/experiments/M3/3dias`.
Runtime capturado: `work/CASE/cases/m3-3days-20180415/work/jedi/20180415T000000Z`.

## Diferenças reais preservadas

| Item | Referência executada |
|---|---|
| JEDI MPI | 128 processos, launcher Cray PALS |
| Endian GNU | `GFORTRAN_CONVERT_UNIT=big_endian:101-200` |
| Outer | `config_dt=1200`, `config_len_disp=240000` |
| Inner | `config_dt=1800`, `config_len_disp=480000` |
| Streams | outer e inner presentes, com listas de campos explícitas |
| Input auxiliar | `templateFields.10242.nc`, estado completo no horário da análise |

A igualdade PT20M = 1200 s aplica-se à trajetória não linear outer. Não foi
demonstrado nesta adaptação que o namelist inner precise ter valores iguais;
preserva-se o arquivo distinto que foi efetivamente usado. A configuração
variacional usa `deallocate non-da fields: true` na geometria inner.

## Uso para 2025

`scripts/create_2025_reference.py` verifica os hashes e copia estes arquivos
para um case novo. A adaptação muda somente o prefixo do nome do output de
`mpas.3dvar` para `mpas.3dfgat` no template variacional, coerente com o contrato
atual de hand-off do workflow. Datas são resolvidas por ciclo.

O gerador utiliza a instalação indicada por `MONAN_JEDI_INSTALL_ROOT` e registra
o SHA-256 do executável JEDI. Não afirma identidade dos binários antigos com os
atuais. O teste de continuidade de duas análises na JACI é obrigatório antes de
liberar a campanha de sete dias de 2025.
