# Command-line run interface

The `xyce-py` console command is an adapter over `XyceProject`, not a separate execution path. The CLI accepts exact netlist files, explicit output declarations, and run-directory controls, then prints a JSON summary. This keeps raw Xyce syntax and advanced analyses behind the existing raw-netlist module while giving command-line users the same output collection contract as Python callers.
