# Modelo de trajetória para 3DVar-FGAT cíclico

## Ideia central

Em 3DVar-FGAT, a janela não deve ser tratada como um único arquivo de
background. A assimilação usa uma **trajetória de forecast** com estados válidos
em vários tempos dentro da janela.

O workflow precisa, portanto, separar:

- tempo da análise;
- origem do forecast que gera a trajetória;
- duração desse forecast;
- tempos ou offsets das saídas que serão disponibilizadas ao JEDI;
- janela temporal usada por cada conjunto de observações.

## Convenção GSI usada no SMNA

Para uma análise em `T` com ciclo de seis horas e janela relativa
`[-3 h, 0 h, +3 h]`:

```text
análise anterior: T - 6 h
início do forecast: T - 6 h
saídas necessárias: T - 3 h, T, T + 3 h
leads do forecast: 3 h, 6 h, 9 h
fim do forecast: T + 3 h
```

Exemplo para análise em `2018-04-15 00Z`:

```text
análise anterior: 2018-04-14 18Z
forecast: 18Z -> 03Z (9 h)

lead 03 h -> 2018-04-14 21Z  (offset -3 h)
lead 06 h -> 2018-04-15 00Z  (offset  0 h)
lead 09 h -> 2018-04-15 03Z  (offset +3 h)
```

O ciclo seguinte, em `06Z`, usa a trajetória produzida pela análise das `00Z`:

```text
forecast: 00Z -> 09Z
saídas usadas: 03Z, 06Z, 09Z
```

Assim, o encadeamento científico é:

```text
analysis(T-6)
  -> forecast(T-6, T+3)
  -> trajectory[T-3, T, T+3]
  -> analysis(T)
```

## Onde configurar

O YAML mínimo do experimento continua sem detalhes de trajetória:

```yaml
cycle:
  start: 2018-04-15T00:00:00Z
  end: 2018-04-16T00:00:00Z
  interval_hours: 6

assimilation:
  method: 3dvar_fgat
```

A configuração grossa do método deve declarar a trajetória padrão:

```yaml
# configs/assimilation/3dvar_fgat.yaml
assimilation:
  method: 3dvar_fgat
  fgat:
    trajectory_offsets_hours: [-3, 0, 3]
    forecast_origin: previous_analysis
```

O perfil de forecast declara como produzir estados compatíveis:

```yaml
# configs/forecast/mpas_fgat_3h.yaml
forecast:
  output_interval_hours: 3
  required_output_offsets_hours: [-3, 0, 3]
```

O resolvedor combina o intervalo do ciclo e a origem da trajetória. Para
`forecast_origin: previous_analysis`, a origem equivale a `-cycle.interval`.
No exemplo de seis horas, a duração necessária é automaticamente nove horas.

## Variações futuras

A arquitetura suporta, sem modificação no motor Python, casos como:

```yaml
# Janela de quatro horas centrada na análise
fgat:
  trajectory_offsets_hours: [-2, 0, 2]

# Janela de seis horas com saídas de hora em hora
fgat:
  trajectory_offsets_hours: [-3, -2, -1, 0, 1, 2, 3]

# Janela assimétrica
fgat:
  trajectory_offsets_hours: [-2, 0, 1, 3]
```

O método pode ainda definir outra origem de forecast quando cientificamente
necessário, desde que ela seja anterior ao primeiro estado solicitado.

## Implicações para o runtime

Cada ciclo deverá registrar:

```yaml
analysis_time: 2018-04-15T00:00:00Z
forecast_start_time: 2018-04-14T18:00:00Z
forecast_end_time: 2018-04-15T03:00:00Z
trajectory:
  - valid_time: 2018-04-14T21:00:00Z
    forecast_lead_hours: 3
    offset_from_analysis_hours: -3
  - valid_time: 2018-04-15T00:00:00Z
    forecast_lead_hours: 6
    offset_from_analysis_hours: 0
  - valid_time: 2018-04-15T03:00:00Z
    forecast_lead_hours: 9
    offset_from_analysis_hours: 3
```

O renderer de MPAS deverá configurar streams/saídas de forma a preservar esses
estados. O renderer JEDI deverá apontar para a trajetória correspondente, não
para um único arquivo de background.
