# Release Runbook

`xyce-py` releases use a staged flow: certify the self-hosted Xyce runners, rehearse
the release candidate on TestPyPI, publish the final release to PyPI, and then run a
clean-room post-publish smoke pass.

## Prerequisites

- GitHub trusted publishing is configured for the `testpypi` and `pypi` environments.
- A Linux self-hosted runner labeled `self-hosted`, `linux`, `xyce` is online.
- A macOS self-hosted runner labeled `self-hosted`, `macos`, `xyce` is online.
- Both self-hosted runners have `Xyce` available on `PATH`.
- Both self-hosted runners have `python3` 3.10 or newer with `venv` support; the workflows install dependencies inside a runner-local virtual environment.
- `security/pip_audit_allowlist.json` is either empty or contains only unexpired entries with a documented owner and reason.

## First-Release Checklist

1. Run `.github/workflows/xyce-runner-smoke.yml` with `workflow_dispatch`.
2. Confirm both Linux and macOS runner jobs pass and record their `Xyce -v` output.
3. Confirm `docs/capability-matrix.md` matches the public support surface.
4. Bump `pyproject.toml` to a prerelease version such as `1.0.1rc1`.
5. Run `.github/workflows/release-candidate.yml` with `workflow_dispatch`.
6. If the workflow fails, fix the issue, bump to the next prerelease such as `1.0.1rc2`, and rerun the rehearsal.
7. After a green rehearsal for the same release line, bump `pyproject.toml` to the final version such as `1.0.1`.
8. Run `.github/workflows/publish.yml` with `workflow_dispatch`.
9. Wait for `.github/workflows/post-publish-smoke.yml` to complete successfully against PyPI.

## Release Candidate Flow

The release-candidate workflow must pass all of these jobs:

- `xyce-release-gate-linux`
- `xyce-release-gate-macos`
- `build-distributions`
- `dependency-audit`
- `publish-to-testpypi`
- `testpypi-wheel-smoke`
- `testpypi-sdist-smoke`

## Final Publish Flow

The final publish workflow must pass all of these jobs:

- `build-distributions`
- `smoke-install`
- `dependency-audit`
- `publish-to-pypi`

## Post-Publish Smoke

`.github/workflows/post-publish-smoke.yml` runs automatically after a successful
`Publish` workflow and can also be triggered manually.

- Automatic runs verify the just-published PyPI release.
- Manual runs can target either PyPI or TestPyPI.
- Wheel and source installs use the Docker clean-room script:
  `tools/cleanroom/run_registry_smoke.sh`
- Upgrade smoke is only required for PyPI releases. It installs the previous final
  release first, runs the standalone smoke harness, upgrades to the target version,
  and reruns the same harness.

For a local clean-room confirmation, run one of:

```bash
python tools/release_smoke.py
tools/cleanroom/run_registry_smoke.sh --index pypi --version 1.0.1 --install-mode wheel
tools/cleanroom/run_registry_smoke.sh --index pypi --version 1.0.1 --install-mode sdist
tools/cleanroom/run_registry_smoke.sh --index pypi --version 1.0.1 --install-mode upgrade --previous-version 1.0.0
```

## Audit Exception Policy

`pip-audit` is release-blocking by default. Temporary exceptions are allowed only
through `security/pip_audit_allowlist.json`.

Every exception entry must contain:

- `id`
- `package`
- `reason`
- `owner`
- `expires_on`

Expired entries fail the release workflow even if the advisory is otherwise ignored.
If an exception is still needed, renew it explicitly with a new `expires_on` date and
updated reason before rerunning the release workflow.

## Release Record

Record these details for every release:

- Runner-smoke workflow URL
- Release-candidate workflow URL
- Publish workflow URL
- Post-publish smoke workflow URL
- The TestPyPI project URL for the rehearsed release candidate
- The Linux Xyce version reported by the runner or release gate workflow
- The macOS Xyce version reported by the runner or release gate workflow
- The dependency-audit summary or artifact URL
- The final PyPI project URL
