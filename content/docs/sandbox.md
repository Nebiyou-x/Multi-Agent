---
title: Sandbox
summary: One throwaway Docker container per code execution, with no network, a read-only root and hard resource caps.
order: 4
---

# Sandbox

The sandbox is where agent-generated Python runs: one throwaway Docker
container per `code_execution` call, spawned by `packages/sandbox/manager.py`
against the image built from `infra/sandbox-image/Dockerfile`
(`agent-sandbox:latest`).

## Threat model

Be explicit about what this is protecting against, because it is narrow:

- **Code is LLM-generated, not user-submitted.** The generated script can
  be wrong, accidental, or mildly malicious (a runaway loop, an `rm -rf`
  the model hallucinated). It is not written by a hostile party trying to
  steal secrets or escape the box.
- **Solo developer, single host.** One person, one machine, one trusted
  user. There is no adversarial boundary between "my code" and "your code"
  because there is no "your code".
- **No multi-tenant guarantees.** Everything here assumes one owner. If
  two users ever share a host through this system, this document stops
  describing reality - the caps and mounts below are per-container, not
  per-tenant, and the Docker socket is shared.

Under that threat model the goal is: generated code can mess with its own
`/out`, consume at most 512m/0.5CPU/30s, and never touch the network, the
host filesystem, or other containers. It can still be slow, dumb, or
noisy - that is a quality problem for the critic, not a security problem.

## Isolation flags, and why each one

The manager builds the container like this (values below are the defaults;
each is env-overridable):

```python
container = client.containers.run(
    image="agent-sandbox:latest",
    command=["python", "/main.py"],
    network_mode="none",       # generated code has no network, ever
    read_only=True,           # root filesystem is read-only
    tmpfs={"/tmp": "size=64m"},
    volumes=[
        "tmp/main.py:/main.py:ro",
        "tmp/in:/in:ro",
        "tmp/out:/out:rw",
    ],
    mem_limit="512m",
    cpu_quota=50000, cpu_period=100000,   # 0.5 CPU
    labels={"agent-sandbox": "ephemeral"},
)
```

Plus the image-level hardening from the Dockerfile. Each flag, by itself:

- **`--network none`** - the load-bearing line. `import socket`,
  `requests`, `httpx` all fail at runtime. Data for the code must arrive as
  an input file from an earlier `http_fetch` / `web_search` / `sql_query`
  step; that separation is a planner rule too, not just a runtime accident.
  Phase2.md's hostile-code probe verifies it: `socket.socket()` raises.
- **`--read-only` root filesystem** - the code cannot write system
  directories, install packages, or drop files in `/`. `rm -rf /` becomes a
  no-op on a read-only rootfs; `cat /bin/sh` still works after. Anything
  that genuinely needs to be written goes to `/tmp` or `/out`.
- **`--tmpfs /tmp` (size=64m)** - the one that surprises people. The
  Dockerfile sets `PYTHONDONTWRITEBYTECODE=1` and `MPLCONFIGDIR=/tmp` so
  Python and matplotlib never write byte-code or config into the rootfs.
  Without a writable `/tmp`, a read-only root would fail the moment
  matplotlib initializes. The tmpfs is also ephemeral: it dies with the
  container. 64m is plenty for a matplotlib font cache and small scratch
  files.
- **`--memory 512m`** - a runaway `sum(range(...))` or a `while True`
  allocator dies on OOM instead of taking down the host. 512m covers the
  demo tasks (World Bank JSON + a line chart); a large dataset analysis
  will need the env override `SANDBOX_MEMORY`.
- **`--cpus 0.5`** - same idea, for CPU: one container cannot starve the
  host or the API service. Overridable via `SANDBOX_CPU`.
- **Wall-clock timeout (`SANDBOX_TIMEOUT`, default 30s)** - the container
  is `kill()`ed and then `remove(force=True)`d even on timeout. An infinite
  loop is a `timed_out: true` result with whatever partial stdout was
  captured, never a hung API request.
- **`/main.py:ro`, `/in:ro`** - the script and the input data are bind
  mounts read-only; the container process runs as uid 1000 (non-root in
  the image), so even its own script file is not writable.
- **`/out:rw` (host dir chmod 0777)** - the one writable location, for
  artifacts. World-writable because the container is uid 1000, not root.
- **stdout/stderr caps (`SANDBOX_OUTPUT_CAP`, default 32768 bytes)** - only
  the tail of a huge dump is kept, and a `warnings` entry says which stream
  was truncated. Base64 blobs in the trace would explode LLM context.
- **Non-root user + `PYTHONDONTWRITEBYTECODE=1` + headless matplotlib**
  (image level) - `useradd --create-home --uid 1000 sandbox`,
  `MPLBACKEND=Agg`, `MPLCONFIGDIR=/tmp/matplotlib`. The image ships
  pandas/numpy/matplotlib so generated code can do the actual work.

The two Phase2.md probes are the acceptance test for the whole layer:

```bash
# works under full hardening -> 49999999950000000
docker run --rm --network none --memory 512m --cpus 0.5 --read-only \
  --tmpfs /tmp -v "$SNIPPET:/main.py:ro" agent-sandbox:latest python /main.py

# hostile code fails safely: rm -rf / is a no-op on read-only rootfs,
# socket call raises because --network none
```

## Artifact capture protocol

1. The manager makes a host-side temp dir: `main.py` (the code), `in/`
   (inputs: structured values written as JSON, plain strings verbatim),
   `out/` (empty, chmod 0777).
2. The container runs; stdout/stderr stream in tail-capped.
3. On finish (or after the timeout kill), files under `out/` are collected
   in sorted name order. Each artifact becomes
   `{"name", "size", "content_b64", "truncated"}` - `content_b64` is set
   only while the file is under `SANDBOX_ARTIFACT_FILE_CAP` (default
   512000 bytes) and the running total is under `SANDBOX_ARTIFACT_CAP`
   (default 1000000 bytes); beyond either cap the entry keeps name + size
   and sets `truncated: true`.
4. The result dict (stdout tail, stderr tail, exit_code, timed_out,
   warnings, duration_ms, artifacts) flows up through `code_execution`
   into the trace step. The executor then strips the base64 blobs from the
   LLM context (name/size/truncated only) - the trace keeps them, the
   prompt does not.
5. After the run, the API's `persist_artifacts` decodes the `content_b64`
   entries and writes them to `data/artifacts/<run_id>/<name>` (skipping
   truncated ones). The executor summarizes only the artifact *names*, so
   the final answer can reference `/out/inflation.png` by name.
6. The container is `remove(force=True)`d and the temp dir deleted. Nothing
   persists between calls.

## Non-goals

- **No network in code execution.** By design. `requests`/`socket`
  failing is a feature; the data pipeline is fetch-then-execute.
- **No persistent filesystem.** `/out` dies with the container; only the
  collected artifacts (copied out) survive, and only below the size caps.
- **No multi-tenant isolation guarantee.** The caps are per-container;
  two tenants on one host share the same socket, the same Docker daemon,
  and the same `data/artifacts/` tree. This is not designed for that.
- **Not a general-purpose CFI, kernel isolation, or security boundary
  against a determined adversary.** `--read-only`, memory caps, and
  `--network none` are cheap containment against sloppy generated code -
  the right amount for the threat model above - and nothing more. A host
  escape or a docker-daemon exploit is out of scope, as it would be for
  any Docker-based sandbox.
