from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from xyce_py.engine import _execute_xyce_netlist, _read_waveforms, XyceRunError, find_xyce_executable


def _xyce_available() -> bool:
    return Path("/usr/local/XyceNF_7.10/bin/Xyce").exists() or shutil.which("Xyce") is not None


class EngineUtilityTests(unittest.TestCase):
    def test_find_xyce_executable_returns_a_string(self):
        self.assertIsInstance(find_xyce_executable(), str)

    def test_read_waveforms_returns_empty_dataframe_for_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            frame = _read_waveforms(Path(tmpdir) / "missing.csv")

        self.assertTrue(frame.empty)


@unittest.skipUnless(_xyce_available(), "Xyce is not available in this environment.")
class EngineExecutionTests(unittest.TestCase):
    def test_execute_xyce_netlist_runs_minimal_op_netlist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            netlist = (
                "* minimal\n"
                "V1 n1 0 10\n"
                "R1 n1 n2 1000\n"
                "R2 n2 0 1000\n"
                ".OP\n"
                ".PRINT DC FORMAT=CSV FILE=out.csv V(n1) V(n2)\n"
                ".END\n"
            )

            result = _execute_xyce_netlist(
                xyce_path=find_xyce_executable(),
                base_out_dir=tmpdir,
                netlist_content=netlist,
                csv_name="out.csv",
                run_name="engine_test",
                keep_run_dir=True,
            )

        self.assertEqual(list(result.waveforms.columns), ["V(N1)", "V(N2)"])
        self.assertEqual(len(result.waveforms), 1)

    def test_execute_xyce_netlist_raises_xyce_run_error_on_bad_netlist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            netlist = "* bad\nTHIS_IS_NOT_VALID_SPICE_SYNTAX\n.END\n"

            with self.assertRaises(XyceRunError):
                _execute_xyce_netlist(
                    xyce_path=find_xyce_executable(),
                    base_out_dir=tmpdir,
                    netlist_content=netlist,
                    csv_name="out.csv",
                    run_name="engine_bad",
                    keep_run_dir=True,
                )


if __name__ == "__main__":
    unittest.main()
