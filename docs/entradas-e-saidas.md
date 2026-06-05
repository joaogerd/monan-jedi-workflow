# Entradas e Saídas

## Entradas principais

### Configurações

```
configs/experiments/3dfgat_mpastatic_x1.10242_2018041500/
```

### Dados externos

- backgrounds MPAS
- geometria MPAS
- tabelas físicas
- observações IODA

---

## Arquivos físicos obrigatórios

```
CAM_ABS_DATA.DBL
CAM_AEROPT_DATA.DBL
COMPATIBILITY
GENPARM.TBL
LANDUSE.TBL
OZONE_DAT.TBL
OZONE_LAT.TBL
OZONE_PLEV.TBL
RRTMG_LW_DATA
RRTMG_LW_DATA.DBL
RRTMG_SW_DATA
RRTMG_SW_DATA.DBL
SOILPARM.TBL
VEGPARM.TBL
```

---

## Arquivos de geometria

```
x1.10242.invariant.nc
x1.10242.graph.info.part.64
namelist.atmosphere.*
streams.atmosphere.*
stream_list.atmosphere.*
```

---

## Arquivos críticos de background

```
templateFields.10242.nc
background/mpasout.*
```

---

## Saídas

### Estados

```
Data/states/
```

### Espaço de observação

```
Data/os/
```

### Logs

```
logs/
```
