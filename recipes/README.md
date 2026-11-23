# MONAN-JEDI experiment recipes

The bundled recipe is [MPAS-JEDI 3DVar/FGAT](../monan_jedi_workflow/recipes/mpas-jedi-3dvar/README.md).
It is installed with the Python package as a complete recipe with README,
`recipe.yaml`, and its own `science/` tree. The legacy `catalog/` reference is
retained temporarily for older integrations only.

Recipes specify scientific defaults. An explicitly supplied create parameter
overrides the corresponding recipe default; omitted values do not override it.
A selected mesh/resolution must resolve *all* dependent scientific resources.
The system must never assume that a 240 km covariance, partition, or invariant
file also works at 120/60/30/15 km.

External recipes may be supplied by path if they include `recipe.yaml`, a
`README.md`, and a `science/` directory with all required scientific files.
