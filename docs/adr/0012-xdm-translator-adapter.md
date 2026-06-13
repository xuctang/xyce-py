# XDM translator adapter

`XdmTranslator` is an external-tool adapter for XDM translation workflows. Callers supply the exact XDM command arguments; `xyce-py` owns subprocess execution, structured failure reporting, working-directory validation, and optional expected-output validation. It does not parse XDM input formats or duplicate XDM command-line semantics.
