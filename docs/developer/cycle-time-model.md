# Modelo temporal do ciclo de assimilação

## Convenção

No estágio JEDI, `cycle` significa **horário da análise**. Essa definição é deliberada e não deve ser trocada por “horário de início da previsão”.

Para o baseline 3D-FGAT usado como referência no desenvolvimento atual:

```text
analysis(t)
   |
   | background_offset = -3 h
   v
FGAT initial state(t-3h) -- xb(t) trajectory --> t+3h
   |
   +-- JEDI produz analysis(t)
                   |
                   +-- MPAS forecast produz o background do próximo ciclo
```

Se o passo entre análises é 6 h:

```text
analysis                2018-04-15 00Z
FGAT initial state      2018-04-14 21Z
next analysis           2018-04-15 06Z
next FGAT initial state 2018-04-15 03Z
previous analysis       2018-04-14 18Z
```

Esses valores são configuração do caso e não constantes do código.

## Por que separar `cycle_step` e `background_offset`

É incorreto inferir o horário do background a partir do intervalo entre análises. Um experimento pode ciclar a cada 6 h e usar um estado válido 3 h antes da análise. Outros métodos podem usar convenções diferentes.

O código portanto mantém explicitamente:

```text
step_hours
background_offset_hours
window_hours
```

## Contexto renderizado

`analysis_cycle_context()` publica grupos de campos:

- `analysis_*`;
- `previous_cycle_*`;
- `next_cycle_*`;
- `background_*`;
- `next_background_*`;
- `window_begin_*`;
- `window_end_*`.

Cada grupo possui representações ISO, `YYYYMMDDHH` e formatos MPAS com `:` ou `.`.

## Invariantes

1. Todas as datas internas são UTC e timezone-aware.
2. `cycle_time == analysis_time` no estágio JEDI.
3. `previous_cycle = analysis - step_hours`.
4. `next_cycle = analysis + step_hours`.
5. `background = analysis + background_offset_hours`.
6. `next_background = next_cycle + background_offset_hours`.
7. O orquestrador não deve repetir essa aritmética.

O estado em T−3 inicializa, mas não representa sozinho, o background do
3D-FGAT. O background é a trajetória `xb(t)` integrada pelo MPAS dentro do
OOPS entre T−3 e T+3. Consulte
[3D-FGAT background trajectory](3dfgat-background-trajectory.md).

## FGAT e versões antigas

Tutoriais antigos do MPAS-JEDI ajudam a entender a sequência análise/previsão, mas não são fonte de verdade para nomes de arquivos, chaves YAML ou detalhes temporais da versão atual. O caso corrente validado deve sempre vencer quando houver divergência.
