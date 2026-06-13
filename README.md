# taskforge

**A declarative task runner in pure Python.** Define build/test/release tasks in
a small `taskforge.yaml`, with dependencies, variable interpolation, a fan-out
matrix, file includes, and dry-run command plans.

Part of the **Cognis Neural Suite**. Standard library only — no pip installs, no
binary to download, runs anywhere Python does (including air-gapped CI).

---

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
