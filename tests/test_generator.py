import tempfile
import unittest
from pathlib import Path

from generate_fusion_chain import (
    build_chain,
    check_neutron_data,
    read_material_nuclides,
)


BASE_CHAIN = """<?xml version="1.0"?>
<depletion_chain>
  <nuclide name="Be9" reactions="0"/>
  <nuclide name="H3" half_life="388789600.0" decay_modes="1" decay_energy="5690.0" reactions="0">
    <decay type="beta-" target="He3" branching_ratio="1.0"/>
  </nuclide>
  <nuclide name="He3" reactions="0"/>
  <nuclide name="He4" reactions="0"/>
  <nuclide name="He6" reactions="0"/>
  <nuclide name="Li6" reactions="0"/>
  <nuclide name="Li7" reactions="0"/>
  <nuclide name="Li8" reactions="0"/>
</depletion_chain>
"""


class GeneratorTests(unittest.TestCase):
    def test_build_chain_and_validate_neutron_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materials = root / "materials.xml"
            cross_sections = root / "cross_sections.xml"
            base = root / "base_chain.xml"
            output = root / "fusion_chain.xml"

            materials.write_text(
                """<materials>
  <material id="1">
    <nuclide name="Li6" ao="0.5"/>
    <nuclide name="Li7" ao="0.4"/>
    <nuclide name="Be9" ao="0.1"/>
  </material>
</materials>\n"""
            )
            base.write_text(BASE_CHAIN)

            # The validator checks both the index and referenced file paths.
            for name in ("Li6", "Li7", "Be9"):
                (root / f"{name}.h5").touch()
            cross_sections.write_text(
                """<cross_sections>
  <library type="neutron" materials="Li6" path="Li6.h5"/>
  <library type="neutron" materials="Li7" path="Li7.h5"/>
  <library type="neutron" materials="Be9" path="Be9.h5"/>
</cross_sections>\n"""
            )

            self.assertEqual(
                read_material_nuclides(materials), {"Li6", "Li7", "Be9"}
            )
            check_neutron_data({"Li6", "Li7", "Be9"}, cross_sections)
            build_chain(base, materials, cross_sections, output)

            result = output.read_text()
            self.assertIn('type="(n,t)"', result)
            self.assertIn('type="(n,Xt)"', result)
            self.assertIn('target="He3"', result)

    def test_missing_neutron_data_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cross_sections = root / "cross_sections.xml"
            cross_sections.write_text(
                '<cross_sections><library type="neutron" '
                'materials="Li6" path="Li6.h5"/></cross_sections>'
            )

            with self.assertRaisesRegex(RuntimeError, "Li7"):
                check_neutron_data({"Li6", "Li7"}, cross_sections)


if __name__ == "__main__":
    unittest.main()
