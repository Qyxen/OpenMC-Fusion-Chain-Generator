"""Public API for the OpenMC fusion depletion-chain generator."""

from .generator import (
    DEFAULT_KEEP,
    build_chain,
    check_neutron_data,
    find_daughter_closure,
    read_material_nuclides,
    read_neutron_library,
)


def main():
    """Run the command-line interface."""
    from .generator import main as _main

    return _main()


__all__ = [
    "DEFAULT_KEEP",
    "build_chain",
    "check_neutron_data",
    "find_daughter_closure",
    "main",
    "read_material_nuclides",
    "read_neutron_library",
]
