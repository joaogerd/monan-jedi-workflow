# ADR 0003 — Matriz B como artefato externo ao ciclo

**Status:** accepted

## Contexto

A matriz B possui uma campanha própria de produção e validação. Misturar esse cálculo com a campanha de assimilação amplia o workflow e permite que um ciclo regenere inadvertidamente um componente científico que deveria permanecer fixo.

## Decisão

O ciclo de assimilação consome uma matriz B previamente produzida, validada e identificável. A produção da B permanece fora do workflow de cycling.

## Consequências

- experimentos podem reutilizar exatamente a mesma B;
- a proveniência fica mais clara;
- `MPAS-BMatrix` e workflows de geração da B evoluem independentemente;
- o estágio JEDI deve validar a disponibilidade dos artefatos declarados, não reconstruí-los.
