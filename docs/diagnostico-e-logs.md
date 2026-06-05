# Diagnóstico e Logs

## Verificar erros reais

```bash
grep -RniE \
"ERROR|FATAL|CRITICAL|Abort|MPI_Abort|No such file|failure opening|does not contain the time" \
. 2>/dev/null | head -200
```

---

## Verificar links simbólicos

```bash
ls -l build/runtime/<exp>/<cycle>
```

---

## Verificar destino do link

```bash
readlink -f templateFields.10242.nc
```

---

## Comparar com baseline

```bash
diff workflow.yaml baseline.yaml
```

---

## Erros clássicos

### OZONE_PLEV.TBL

Causa:

Arquivos físicos ausentes.

### templateFields does not contain time

Causa:

Arquivo errado utilizado.

### geometry initialization failure

Causa:

Arquivos de geometria incompletos.
