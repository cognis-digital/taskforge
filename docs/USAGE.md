# taskforge — Usage Guide

A declarative task runner: define tasks with dependencies, variables, a fan-out
matrix, and file includes, then run, plan, graph, or validate them.

## Task file

```yaml
vars:
  app: hello-edge
  registry: localhost:5000

tasks:
  build:
    desc: Build the app.
    deps: [clean]
    cmds:
      - echo building ${app}

  test:
    deps: [build]
    matrix:
      py: ["3.10", "3.12"]
    cmds:
      - echo testing ${app} on python ${py}

  release:
    deps: [test]
    cmds:
      - echo publishing ${app} to ${registry}
```

## Variable precedence

Highest to lowest:
1. `--var K=V` CLI overrides
2. matrix values
3. task `vars`
4. file `vars`
5. process environment (`${HOME}`, etc.)

Unknown `${X}` is left intact (not blanked), so shell vars pass through.

## Commands

```bash
# Run a task and its dependencies.
python -m taskforge run release

# Preview the plan (deps + matrix + interpolation), nothing executed.
python -m taskforge run release --dry-run

# Override variables at the command line.
python -m taskforge run release --var registry=ghcr.io/cognis --var app=edge

# List tasks; show a task's resolved run order.
python -m taskforge list
python -m taskforge graph release

# Validate the whole file: unknown deps, cycles, and missing commands.
python -m taskforge validate

# MCP server (list / plan / run).
python -m taskforge mcp
```

## Includes

```yaml
includes:
  - ../shared/base.yaml   # merged first; later files override task names
vars:
  app: my-service
tasks:
  deploy:
    deps: [common]        # a task defined in base.yaml
    cmds: [echo deploying ${app}]
```

## Matrix fan-out

A task with a `matrix` runs once per combination of its named value lists:

```yaml
test:
  matrix:
    py: ["3.10", "3.12"]
    os: [linux, darwin]
  cmds: [echo test ${py} on ${os}]   # 4 invocations
```

## CI recipe

```bash
python -m taskforge validate || exit 1          # catch cycles/typos first
python -m taskforge run release --var registry=$CI_REGISTRY
```
