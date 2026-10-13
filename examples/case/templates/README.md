# Templates científicos do caso de referência 2025

Copie o diretório completo com o caso. Os YAMLs consomem:

- `namelist.atmosphere.cycling.in` e `streams.atmosphere.cycling.in`: forecast cíclico;
- `namelist.atmosphere.initial.in` e `streams.atmosphere.initial.in`: forecast de inicialização;
- `namelist.atmosphere.jedi.in`: namelists outer/inner do MPAS-JEDI;
- `variational.yaml`: 3D-FGAT, B, observers, QC e minimização.

Os templates de WPS e mpas_init permanecem em `../initialization/templates/`.
Os campos entre chaves são preenchidos pelo materializador por ciclo; não são
instruções para editar datas manualmente. Confira as referências em cada YAML.

Este baseline usa x1.10242, 55 níveis e PREPBUFR (radiossondas e superfície) e GNSS-RO.
`variational.yaml` preserva a configuração SABER/BUMP, operadores, QC e
minimização de `experiments/M3/3dias/configs/jedi/20180415T000000Z/3dfgat.bmatrix.yaml`
no repositório `GAD-DIMNT-CPTEC/monan-jedi-2026`, commit
`5aeed60857447bf229416327441589ca52e29e39`. Datas e caminhos são parametrizados.
A presença dos templates no Git não comprova execução científica na JACI.
Use o preflight do caso copiado e valide os logs e produtos antes de ampliar
P7D para P30D. Tabelas de física e matriz B continuam sendo dados externos.
