# CircuitGraph output artifacts

`CircuitGraph.simulate()` can collect declared `OutputSpec` artifacts into `SolveResult.outputs` when `keep_run_dir=True`. Extra output artifacts require a kept run directory because `OutputArtifact.path` must remain valid after return. Graph-level `.MEASURE` support is stored as structured `MeasureDirective` objects and emitted after node compilation so exact `V(user_node)` references can be translated to generated SPICE node names without exposing those generated names in the public graph interface.
