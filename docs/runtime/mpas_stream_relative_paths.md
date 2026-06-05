# MPAS Stream Relative Paths

MPAS resolves filenames declared inside `streams.atmosphere.*` relative to the
process execution directory. They are not resolved relative to the directory
that contains the `streams_file`.

This matters for 3DFGAT because the JEDI YAML can point to absolute
`nml_file` and `streams_file` paths while the MPAS streams still contain
relative entries such as:

```xml
filename_template="x1.10242.invariant.nc"
filename_template="templateFields.10242.nc"
<file name="stream_list.atmosphere.background"/>
```

For the x1.10242 3DFGAT runtime, `prepare_runtime` must place these files
directly in `RUNTIME_DIR`:

- `x1.10242.invariant.nc`
- `templateFields.10242.nc`
- `x1.10242.graph.info.part.64`
- `stream_list.atmosphere.background`
- `stream_list.atmosphere.analysis`
- `stream_list.atmosphere.ensemble`
- `stream_list.atmosphere.control`

`templateFields.10242.nc` must also contain the initial FGAT time
`2018-04-14_21:00:00`. For the tutorial case it should point to the 21Z
background file, not the 00Z smoke-state file.

The runtime preparation step validates these paths before PBS submission so
missing relative stream inputs fail early.

The rendered 3DFGAT YAML also gives OOPS an absolute background path under
`${MONAN_SCRATCH}/jaci_3dvar_fgat_tutorial_2018041500/background`. Before PBS
submission, `prepare_3dvar_fgat_runtime.sh --strict` must stage the same 21Z
background there:

```text
${MONAN_SCRATCH}/jaci_3dvar_fgat_tutorial_2018041500/background/mpasout.2018-04-14_21.00.00.nc
```

This scratch link is separate from MPAS stream-relative files in `RUNTIME_DIR`,
but it must resolve to the same validated 21Z background with xtime
`2018-04-14_21:00:00`.
