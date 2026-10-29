"""
The biochem pack — Saturn for wet bio and chemistry labs.

Toolkits:
  labmath — dilutions, molar solutions, serial dilutions, buffer recipes, molecular weight.
            Exact bench arithmetic with units (pint) and formula masses (molmass), so a small
            local model never works a concentration out in its head.

Turn it on with `/tools on labmath`. Install its dependencies with
`pip install 'saturn-agent[biochem]'`.
"""

from tools.toolspec import Toolkit

TOOLKITS = {
    "labmath": Toolkit(
        "Lab math",
        "dilutions, molar solutions, serial dilutions, buffers, molecular weight",
        pack="biochem",
        prompt=("- Lab calculations — dilutions, molar solutions, serial dilutions, buffer "
                "recipes, molecular weights — come from dilution, molar_solution, "
                "serial_dilution, buffer_recipe and molecular_weight, never from your own "
                "arithmetic. Pass every quantity with its unit, as the user wrote it "
                "(\"10 mM\", \"50 uL\", \"2 mg/mL\")."),
    ),
}

MODULES = ("labmath",)
