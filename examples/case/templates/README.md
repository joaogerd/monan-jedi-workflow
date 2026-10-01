# Templates científicos

Este diretório contém os arquivos consumidos por MONAN/MPAS e MPAS-JEDI.

Antes de executar um caso real, forneça:

- `namelist.atmosphere`: forecast cíclico;
- `streams.atmosphere`: forecast cíclico e frequência dos DA states;
- `namelist.atmosphere.initial`: inicialização do primeiro background;
- `streams.atmosphere.initial`: outputs da inicialização;
- `namelist.atmosphere.jedi`: geometry/model usado pelo MPAS-JEDI;
- `variational.yaml`: método DA, B, observers, operadores, QC e minimização.

O repositório não fornece valores científicos universais para esses arquivos.
O baseline 2025 validado substituirá os placeholders deste template.
