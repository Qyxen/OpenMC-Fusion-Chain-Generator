# OpenMC Fusion Depletion Chain Generator

Creates a reduced OpenMC depletion chain for fusion blanket materials.
The generator reads the nuclides in an OpenMC `materials.xml`, checks that
each nuclide has neutron data in the selected `cross_sections.xml`, and
combines them with the lithium breeder reaction paths.

The generated chain includes:

- Li-6 `(n,t)` production of H-3
- Li-7 MT=205 `(n,Xt)` tritium production
- H-3 beta-minus decay to He-3
- All nuclides found in the supplied materials file

## Requirements

- OpenMC 0.16 or newer
- Python with the OpenMC package available
- A base OpenMC depletion-chain XML file
- An OpenMC `materials.xml` file
- An OpenMC `cross_sections.xml` file

## Installation

From the project directory:

```bash
pip install -e .
```

OpenMC is installed separately because it is distributed through conda-forge
rather than the PyPI package index used for this project:

```bash
conda install -c conda-forge openmc
```

After installation, the generator can be imported from any working directory:

```python
import generate_fusion_chain
```

## Python API

The main user-facing function is `build_chain`:

```python
from pathlib import Path
from generate_fusion_chain import build_chain

build_chain(
    base_file=Path("/path/to/chain_endfb81_fast.xml"),
    materials_file=Path("/path/to/materials.xml"),
    cross_sections_file=Path("/path/to/cross_sections.xml"),
    output_file=Path("chain_fusion_breeder.xml"),
)
```

The helper functions are also available:

```python
from generate_fusion_chain import (
    read_material_nuclides,
    read_neutron_library,
    check_neutron_data,
)

nuclides = read_material_nuclides(Path("materials.xml"))
library = read_neutron_library(Path("cross_sections.xml"))
check_neutron_data(nuclides, Path("cross_sections.xml"))
```

`build_chain` validates neutron-data availability before writing the output.
It raises `RuntimeError` with the missing nuclide or data-file paths when the
selected library is incomplete.

## Using the generated chain

MT=205 is represented by the custom `(n,Xt)` reaction. Import the generator
module before creating the depletion operator so that this reaction is
registered with OpenMC:

```python
import sys
sys.path.insert(0, "/path/to/OpenMC-Fusion-Depletion-Chain-Generator")
import generate_fusion_chain  # registers (n,Xt)

operator = openmc.deplete.CoupledOperator(
    model,
    "chain_fusion_breeder.xml",
    normalization_mode="energy-deposition",
)
```

The generator does not modify the input materials, cross-section library, or
base chain files.
