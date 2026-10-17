#!/usr/bin/env python3
"""Generate a reduced OpenMC depletion chain for a fusion breeder blanket.

The stock ENDF/B-VIII.1 chain in this directory does not include the
tritium-producing lithium reactions.  This script preserves the relevant
decay data from the stock chain and adds:

    Li-6(n,t)He-4 + H-3       (MT=105)
    Li-7(n,Xt) + H-3          (MT=205, inclusive channel)
    H-3 beta-minus decay to He-3

The custom ``(n,Xt)`` reaction is registered with OpenMC at runtime because
OpenMC 0.16 does not include MT=205 in its built-in depletion reaction map.
The registration must also be performed by any depletion driver before it
loads the generated chain.
"""

from __future__ import annotations

import argparse
import copy
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from openmc.deplete import Chain
from openmc.deplete.chain import REACTIONS, ReactionInfo


# ENDF MT=205 is an inclusive tritium-production channel.  There is no
# single residual nuclide to track, so the residual target is left as None;
# H-3 is represented as a light-particle secondary.
REACTIONS["(n,Xt)"] = ReactionInfo({205}, ("H3",))


DEFAULT_KEEP = {
    # Lithium breeder isotopes and the tritium decay pair
    "Li6",
    "Li7",
    "H3",
    "He3",
    # Products/decay daughters needed by the lithium reaction paths
    "He4",
    "He6",
    "Li8",
}


def read_material_nuclides(materials_file: Path) -> set[str]:
    """Return all nuclide names appearing in an OpenMC materials XML file."""

    root = ET.parse(materials_file).getroot()
    names = {
        element.get("name")
        for element in root.iter("nuclide")
        if element.get("name")
    }
    if not names:
        raise RuntimeError(f"No <nuclide name=...> entries found in {materials_file}")
    return names


def read_neutron_library(cross_sections_file: Path) -> dict[str, Path]:
    """Read the nuclide-to-file map from an OpenMC cross_sections.xml file."""

    root = ET.parse(cross_sections_file).getroot()
    library = {}
    for element in root.findall("library"):
        if element.get("type") != "neutron":
            continue
        materials = element.get("materials", "")
        path = element.get("path")
        if not path:
            continue
        data_path = Path(path)
        if not data_path.is_absolute():
            data_path = cross_sections_file.parent / data_path
        for name in re.split(r"[\s,]+", materials.strip()):
            if name:
                library[name] = data_path
    return library


def check_neutron_data(
    material_nuclides: set[str], cross_sections_file: Path
) -> None:
    """Fail if any material nuclide lacks an indexed neutron library file."""

    neutron_library = read_neutron_library(cross_sections_file)
    missing = sorted(name for name in material_nuclides if name not in neutron_library)
    missing_files = sorted({
        str(neutron_library[name])
        for name in material_nuclides
        if name in neutron_library and not neutron_library[name].is_file()
    })

    if missing or missing_files:
        message = [
            f"Neutron-data check failed for {cross_sections_file}.",
        ]
        if missing:
            message.append("Nuclides absent from the neutron library index:")
            message.extend(f"  - {name}" for name in missing)
        if missing_files:
            message.append("Indexed neutron-data files that do not exist:")
            message.extend(f"  - {path}" for path in missing_files)
        raise RuntimeError("\n".join(message))


def build_chain(
    base_file: Path,
    materials_file: Path,
    cross_sections_file: Path,
    output_file: Path,
) -> None:
    """Build and export the reduced fusion-breeder chain."""

    material_nuclides = read_material_nuclides(materials_file)
    check_neutron_data(material_nuclides, cross_sections_file)

    base = Chain.from_xml(str(base_file))
    keep = DEFAULT_KEEP | material_nuclides

    missing = sorted(name for name in keep if name not in base)
    if missing:
        raise RuntimeError(
            "The following requested nuclides are absent from the base chain: "
            + ", ".join(missing)
        )

    chain = Chain()

    # Copy only selected nuclides and remove reaction paths whose products are
    # not part of the reduced chain. Decay modes are retained unchanged.
    for name in sorted(keep):
        nuclide = copy.deepcopy(base[name])
        # Keep reaction paths even when their daughter is outside the reduced
        # chain.  Setting target=None preserves the destruction rate and the
        # original branching-ratio sum; deleting the path can leave a reaction
        # type with branching ratios that no longer sum to one.
        nuclide.reactions = [
            reaction
            if reaction.target is None or reaction.target in keep
            else reaction._replace(target=None)
            for reaction in nuclide.reactions
        ]
        chain.add_nuclide(nuclide)

    # Add Li-6(n,t). OpenMC's standard (n,t) reaction map automatically adds
    # H-3 as a secondary and the explicit target is He-4.
    chain["Li6"].add_reaction(
        type="(n,t)",
        target="He4",
        Q=4.783388e6,
        branching_ratio=1.0,
    )

    # Add Li-7 MT=205. The residual products are inclusive/unresolved, so only
    # H-3 is tracked as a secondary and no single residual target is assigned.
    chain["Li7"].add_reaction(
        type="(n,Xt)",
        target=None,
        Q=0.0,
        branching_ratio=1.0,
    )

    # add_reaction mutates the nuclide but does not update Chain.reactions.
    for reaction_name in ("(n,t)", "(n,Xt)"):
        if reaction_name not in chain.reactions:
            chain.reactions.append(reaction_name)

    chain.validate(strict=True)
    chain.export_to_xml(str(output_file))

    print(f"Wrote {output_file}")
    print(f"Nuclides: {len(chain.nuclides)}")
    print("Reactions: " + ", ".join(chain.reactions))
    print("H3 decay modes: " + ", ".join(
        f"{mode.type}->{mode.target}" for mode in chain["H3"].decay_modes
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--materials",
        type=Path,
        required=True,
        help="OpenMC materials.xml file",
    )
    parser.add_argument(
        "--base",
        type=Path,
        required=True,
        help="Base depletion chain XML file",
    )
    parser.add_argument(
        "--cross-sections",
        type=Path,
        default=None,
        help=(
            "OpenMC cross_sections.xml file. If omitted, use the "
            "OPENMC_CROSS_SECTIONS environment variable."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("chain_fusion_breeder.xml"),
        help="Output depletion chain XML",
    )
    args = parser.parse_args()

    cross_sections = args.cross_sections
    if cross_sections is None:
        configured = os.environ.get("OPENMC_CROSS_SECTIONS")
        if configured:
            cross_sections = Path(configured)
        else:
            parser.error(
                "Specify --cross-sections or set OPENMC_CROSS_SECTIONS."
            )

    for path, label in (
        (args.materials, "materials XML"),
        (args.base, "base chain XML"),
        (cross_sections, "cross_sections XML"),
    ):
        if not path.is_file():
            parser.error(f"{label} does not exist: {path}")

    try:
        build_chain(args.base, args.materials, cross_sections, args.output)
    except RuntimeError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
