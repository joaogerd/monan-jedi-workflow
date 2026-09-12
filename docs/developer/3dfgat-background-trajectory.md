# 3D-FGAT background trajectory

## Contrato temporal

Para uma análise no horário T com janela de seis horas:

- T−3 é o **FGAT trajectory initial state**;
- `xb(t)`, de T−3 a T+3, é a **FGAT background trajectory**;
- T possui separadamente o **analysis base state**, o estado MPAS completo que
  inicializa o arquivo de saída;
- após a assimilação, esse arquivo contém o **analysis state**.

O arquivo em T−3 não é todo o background FGAT. O OOPS executa o nonlinear MPAS
e GetValues amostra a trajetória no horário apropriado de cada observação.

## Limitação da interface auditada

Na versão MPAS-JEDI `19eb7fb3273c7b3094825201af184834c15afdd0`, e no
`develop` auditado em 24 de agosto de 2026, cada `Model::step()` chama uma única
propagação física `atm_do_timestep(config_dt)`. Depois, a camada C++ avança o
tempo lógico por `model.tstep`. Não há loop interno nem timestep final para
completar uma duração lógica diferente.

Consequentemente, o contrato obrigatório é:

```text
duration(model.tstep) == config_dt
```

O baseline anterior combinava `PT45M` com `config_dt=1800 s`: seis horas
lógicas continham apenas quatro horas de integração física. Combinar `PT45M`
com o `config_dt=1200 s` de x1.10242 produziria apenas 2h40 físicas. Ambas as
combinações são rejeitadas pelo preflight.

## Configuração x1.10242

```yaml
model:
  name: MPAS
  tstep: PT20M
```

O outer namelist usa `config_dt=1200 s`, `config_len_disp=240000 m`, física
`mesoscale_reference`, ozônio climatológico e DA cycling sem IAU. O outer é o
nonlinear model; o inner mantém sua função de geometria do incremento. Streams
de JEDI permanecem distintos dos streams do forecast.

GetValues usa explicitamente:

```yaml
get values:
  time interpolation: nearest
```

Isso preserva o mecanismo já auditado. Com estados a cada 20 minutos, o
deslocamento temporal nominal máximo entre observação e estado mais próximo é
10 minutos. Interpolação linear não está habilitada.

## Exemplo corrigido para análise 06Z

```text
FGAT initial                                                    end
03:00--03:20--03:40--...--05:40--06:00--06:20--...--08:40--09:00
                              T
                              |
                    analysis base state
                              |
                       analysis state
```

São 18 chamadas do modelo e 19 estados, incluindo os extremos.

## Relação com o SMNA

O SMNA materializava first guesses externos em 03Z, 06Z e 09Z. Neste
OOPS/MPAS-JEDI, um estado externo em 03Z inicializa uma trajetória MPAS interna
a cada 20 minutos até 09Z. As abordagens têm papéis conceituais análogos, mas
não se afirma equivalência numérica.

Referências oficiais:

- [JEDI 3D-FGAT](https://jointcenterforsatellitedataassimilation-jedi-docs.readthedocs-hosted.com/en/latest/inside/jedi-components/oops/algorithmic_details/3d-fgat.html)
- [OOPS source](https://github.com/JCSDA/oops)
- [MPAS-JEDI source](https://github.com/JCSDA/mpas-jedi)
