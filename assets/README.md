Drop optional 3D assets here. The viewer checks whether `Column.glb` exists
via `/viewer/model-manifest.json` before making any GLB request.
If this file is absent, only the generated demo columns are displayed.

Optional spatial workbook: place exactly one .xlsx here (e.g. luoD.xlsx).
Its images and drawing shapes are parsed at startup into A1-origin XY
coordinates with reference pixel and EMU units. Temporary ~$ files are ignored.
