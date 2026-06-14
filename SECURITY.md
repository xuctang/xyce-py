# Security Policy

## Supported Versions

`xyce-py` provides security fixes for the latest public release line.

| Version | Supported |
| --- | --- |
| 1.0.x | Yes |
| Earlier versions | No |

Prerelease versions published to TestPyPI are release-candidate artifacts only
and are not supported after the corresponding final release is published.

## Reporting a Vulnerability

Report suspected vulnerabilities privately through GitHub Security Advisories
for `xuctang/xyce-py`. If that path is unavailable, email the maintainer listed
in `pyproject.toml` with `xyce-py security` in the subject.

Please include:

- affected `xyce-py` version;
- Python version and operating system;
- whether the issue involves raw netlists, generated netlists, output parsing,
  subprocess execution, or packaging;
- a minimal reproduction when safe to share.

Expected handling:

- acknowledgement within 7 days;
- initial assessment within 14 days;
- coordinated fix, release, and advisory when the issue is confirmed.

## Scope

This policy covers vulnerabilities in the `xyce-py` wrapper, including Python
input validation, file handling, subprocess invocation, output collection,
packaging, and release automation.

Vulnerabilities in the Sandia Xyce simulator, XDM, ADMS, model code, or external
netlist content should be reported to the responsible upstream project. When an
upstream simulator issue affects `xyce-py` users, this project may document the
impact or add wrapper-side mitigations, but it does not own the simulator fix.
