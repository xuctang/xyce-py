# Changelog

All notable public changes to `xyce-py` are documented here.

## 1.0.0 - 2026-06-13

### Added

- Public `CircuitGraph` topology interface backed by an internal
  `networkx.MultiDiGraph`.
- Typed helpers for common circuit elements, devices, analyses, directives,
  measurements, sweeps, output artifacts, and solved graph projection.
- Raw `XyceProject` execution for exact Xyce netlists.
- Configurable exact-text feature specs for advanced Xyce analyses, devices,
  models, output/report declarations, XDM workflows, and ADMS workflows.
- Command-line `xyce-py run` wrapper for exact netlist execution.

### Documented

- API reference for exported public functions, classes, methods, parameters,
  return values, and error modes.
- Capability matrix that distinguishes typed support, raw support, configurable
  support, partial support, and planned support.
- Zero-preparation setup path for users who need to install and configure Xyce.
- Example notebooks for beginner circuit construction, raw netlist workflows,
  configurable feature specs, and design sweeps.

### Tested

- Unit, property, integration, packaging, and release-smoke tests for the
  wrapper-owned contracts.
- Real-Xyce integration tests for supported simulation paths when Xyce is
  available.
- Documentation and example drift checks.
- Package coverage gate for the public package modules.

### Packaged

- MIT license declaration.
- `py.typed` marker for typed Python users.
- Lean wheel containing installable package files and metadata.
- Source distribution containing package source, tests, docs, examples,
  release tools, and public source-adjacent material.
- GitHub Actions workflows for CI, release candidates, final PyPI publish,
  post-publish smoke tests, dependency audit, and Xyce runner smoke tests.
