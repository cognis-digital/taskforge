# taskforge

**A declarative task runner in pure Python.** Define build/test/release tasks in
a small `taskforge.yaml`, with dependencies, variable interpolation, a fan-out
matrix, file includes, and dry-run command plans.

Part of the **Cognis Neural Suite**. Standard library only — no pip installs, no
binary to download, runs anywhere Python does (including air-gapped CI).

---


<!-- cognis:example:start -->
## 🔎 Example output

Real, reproducible output from the tool — runs offline:

```console
$ taskforge-emit --version
taskforge 0.1.0
```

```console
$ taskforge-emit --help
usage: taskforge [-h] [--version] [-f FILE] {run,list,graph,validate,mcp} ...

Declarative task runner — deps, variable interpolation, matrix fan-out,
includes, and dry-run command plans.

positional arguments:
  {run,list,graph,validate,mcp}
    run                 Run a task (and its dependencies).
    list                List the tasks defined in the file.
    graph               Show the resolved run order for a task.
    validate            Validate deps, cycles, and commands.
    mcp                 Run as an MCP server (stdio JSON-RPC).

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  -f, --file FILE       Task file (default: taskforge.yaml).
```

> Blocks above are real `taskforge` output — reproduce them from a clone.

**Sample result format** _(illustrative values — run on your own data for real findings):_

```
{
"taskforge": {
"platform": "stix",
"findings": [
{
"id": "1234567890",
"name": "Suspicious Network Traffic",
"description": "Network traffic detected from unknown IP address",
"type": "indicator"
},
{
"id": "2345678901",
"name": "Malware Detection",
"description": "Malware detected on compromised host",
"type": "attack-pattern"
}
]
}
}
```

<!-- cognis:example:end -->

## A task file

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

## Commands

```bash
# Run a task and its dependencies.
python -m taskforge run release

# Preview the exact command plan (deps + matrix + interpolation), no execution.
python -m taskforge run release --dry-run

# List tasks; show a task's resolved run order.
python -m taskforge list
python -m taskforge graph release

# Run as a local MCP server (stdio JSON-RPC).
python -m taskforge mcp
```

## What sets taskforge apart

- **Matrix fan-out.** A task runs once per combination of named value lists —
  no copy-pasted task variants.
- **Composable.** `includes:` merge task files; later definitions override
  earlier names, so teams can share a base and specialize.
- **Safe by default.** Dependency cycles and unknown tasks are caught before
  anything runs; execution is fail-fast.
- **MCP-native** (`list` / `plan` / `run`) and an opt-in local-fleet AI hook
  (default OFF) that drafts a task file from a plain-English pipeline.
- **Zero dependencies.**

## Tests

```bash
python -m pytest -q     # or: python -m unittest discover -s tests
```

## Interoperability

`taskforge` composes with the 300+ tool Cognis suite — JSON in/out and a shared
OpenAI-compatible `/v1` backbone. See **[INTEROP.md](INTEROP.md)** for the
suite map, composition patterns, and reference stacks.

## Integrations

Forward `taskforge`'s findings to STIX/MISP/Sigma/Splunk/Elastic/Slack/webhooks via
[`cognis-connect`](https://github.com/cognis-digital/cognis-connect). See **[INTEGRATIONS.md](INTEGRATIONS.md)**.

## License

Cognis Open Collaboration License (COCL) 1.0 — see [`LICENSE`](LICENSE).
© 2026 Cognis Digital LLC. Original Cognis work; no third-party code, names, or
branding.

<!-- cognis:domains:start -->
## Domains

**Primary domain:** Cyber & Security  ·  **JTF MERIDIAN division:** NULLBYTE · SPECTER

**Topics:** `cognis` `security` `infosec` `cybersecurity` `blue-team`

Part of the **Cognis Neural Suite** — 300+ source-available tools organized across 12 domains under the JTF MERIDIAN command structure. See the [suite on GitHub](https://github.com/cognis-digital) and [jtf-meridian](https://github.com/cognis-digital/jtf-meridian) for how the pieces fit together.
<!-- cognis:domains:end -->

## Usage — step by step

`taskforge` runs declarative tasks from a `taskforge.yaml` with dependencies, variable interpolation, a fan-out matrix, and dry-run plans.

1. **Install** (pure stdlib, Python 3.10+):
   ```bash
   pip install "git+https://github.com/cognis-digital/taskforge.git"
   ```
2. **List and validate** the tasks defined in the file (`-f` points at a non-default path; `validate` checks deps and cycles):
   ```bash
   taskforge list
   taskforge validate
   ```
3. **Preview the command plan** for a task — deps + matrix + interpolation, with nothing executed:
   ```bash
   taskforge run release --dry-run
   taskforge graph release          # just the resolved run order
   ```
4. **Run it** (deps run first), overriding variables at the highest precedence:
   ```bash
   taskforge run release --var registry=ghcr.io/cognis
   ```
5. **Automate in CI** — `run` exits non-zero on the first failing step; `--format json` feeds the result to other tooling:
   ```bash
   taskforge run test --format json
   ```
   Or run it as a local MCP server (stdio JSON-RPC): `taskforge mcp`.
