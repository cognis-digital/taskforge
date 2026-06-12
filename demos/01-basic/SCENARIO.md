# Demo 01 — A build/test/release pipeline

`taskforge.yaml` defines four tasks with dependencies, variables, and a test
**matrix** across Python versions.

## Run it

```bash
# See what would run, in order, with the matrix expanded (nothing executed).
python -m taskforge -f demos/01-basic/taskforge.yaml run release --dry-run

# List tasks and their dependencies.
python -m taskforge -f demos/01-basic/taskforge.yaml list

# Show the resolved run order for a task.
python -m taskforge -f demos/01-basic/taskforge.yaml graph release

# Actually execute it.
python -m taskforge -f demos/01-basic/taskforge.yaml run build
```

## What you should see

`run release --dry-run` expands to:

```
[clean] $ echo cleaning hello-edge
[build] $ echo building hello-edge
[test {'py': '3.10'}] $ echo testing hello-edge on python 3.10
[test {'py': '3.12'}] $ echo testing hello-edge on python 3.12
[release] $ echo publishing hello-edge to localhost:5000
```

Dependencies resolve in topological order, variables interpolate from file +
task + matrix scope, and the `test` task fans out across the matrix.
