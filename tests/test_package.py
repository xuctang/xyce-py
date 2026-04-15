from __future__ import annotations

import unittest

import xyce_py
from xyce_py import CircuitGraph, Resistor, XyceRunError
from xyce_py import compiler, engine, graph, models


class PackageImportTests(unittest.TestCase):
    def test_top_level_exports_match_module_definitions(self):
        self.assertIs(CircuitGraph, graph.CircuitGraph)
        self.assertIs(Resistor, models.Resistor)
        self.assertIs(XyceRunError, engine.XyceRunError)

    def test_module_level_imports_remain_available(self):
        self.assertIs(xyce_py.NetlistCompiler, compiler.NetlistCompiler)
        self.assertIs(xyce_py.CircuitGraph, graph.CircuitGraph)
        self.assertIs(xyce_py.Resistor, models.Resistor)


if __name__ == "__main__":
    unittest.main()
