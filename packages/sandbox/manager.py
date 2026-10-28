"""Ephemeral Docker sandbox for executing agent-generated Python code.

Security model (defense in depth):
- Image: non-root user, no byte-code writing, headless matplotlib (Dockerfile)
- Run:   --network none, read-only rootfs, /tmp tmpfs, memory + CPU caps
- I/O:   inputs bind-mounted READ-ONLY at /in, artifacts collected from /out
- Wall-clock: the container is killed after the timeout; the container itself
  is destroyed after every execution (ephemeral by design)

The generated code can NEVER have network access: the container runs with
network_mode="none". Any network need goes through the http_fetch / web_search
tools first, and the data arrives here as an input file.
"""

import asyncio
import base64
import json
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

try:
    import docker
    from docker.errors import ImageNotFound
except ImportError:
    docker = None
    ImageNotFound = Exception

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_IMAGE = os.getenv("SANDBOX_IMAGE", "agent-sandbox:latest")
DEFAULT_BUILD_DIR = REPO_ROOT / "infra" / "sandbox-image"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


class SandboxManager:
    """Spins up one throwaway container per code execution."""

    def __init__(self, image: str = None, build_dir: Path = None):
        if docker is None:
            raise RuntimeError("The 'docker' Python SDK is not installed. `pip install docker`")
        self.client = docker.DockerClient()
        self.image = image or DEFAULT_IMAGE
        self.build_dir = build_dir or DEFAULT_BUILD_DIR

    # ------------------------------------------------------------------
    def ensure_image(self) -> None:
        """Build the sandbox image on first use if it is missing."""
        try:
            self.client.images.get(self.image)
            return
        except ImageNotFound:
            pass
        build_path = Path(self.build_dir)
        if not (build_path / "Dockerfile").is_file():
            raise FileNotFoundError(f"No Dockerfile for image {self.image!r} at {build_path}")
        self.client.images.build(path=str(build_path), tag=self.image, rm=True)

    # ------------------------------------------------------------------
    def _prepare_workdir(self, code: str, input_files: Dict[str, object]) -> str:
        tmp = tempfile.mkdtemp(prefix="sandbox-")
        (Path(tmp) / "main.py").write_text(code, encoding="utf-8")
        in_dir = Path(tmp) / "in"
        in_dir.mkdir()
        for name, content in (input_files or {}).items():
            # Reject anything that is not a flat basename - path traversal
            if not isinstance(name, str) or name in (".", "..", ""):
                raise ValueError(f"Invalid input file name: {name!r}")
            safe = os.path.basename(name)
            if safe != name or ".." in name:
                raise ValueError(f"Input file names must be flat basenames, got {name!r}")
            if isinstance(content, (bytes, bytearray)):
                data: bytes = bytes(content)
            else:
                data = json.dumps(content, default=str).encode("utf-8")
            (in_dir / safe).write_bytes(data)
        out_dir = Path(tmp) / "out"
        out_dir.mkdir()
        # Bind mounts keep host ownership; the container process is uid 1000
        # (non-root in the image), so /out must be world-writable on Linux.
        out_dir.chmod(0o777)
        return tmp

    def _collect_artifacts(self, out_dir: Path, total_cap: int) -> List[dict]:
        per_file_cap = _env_int("SANDBOX_ARTIFACT_FILE_CAP", 512_000)
        artifacts: List[dict] = []
        total = 0
        for f in sorted(out_dir.iterdir()):
            if not f.is_file():
                continue
            size = f.stat().st_size
            entry: dict = {"name": f.name, "size": size, "content_b64": None, "truncated": False}
            if size <= per_file_cap and total + size <= total_cap:
                entry["content_b64"] = base64.b64encode(f.read_bytes()).decode("ascii")
                total += size
            else:
                entry["truncated"] = True  # too big to inline - name/size only
            artifacts.append(entry)
        return artifacts

    # ------------------------------------------------------------------
    def run_code_sync(
        self,
        code: str,
        input_files: Optional[Dict[str, object]] = None,
        *,
        timeout: int = None,
        memory: str = None,
        cpu: float = None,
        output_cap: int = None,
        on_line: Optional[Callable[[str, str], None]] = None,
    ) -> dict:
        """Run `code` in a fresh container. Returns stdout/stderr, exit code,
        timed_out flag, duration and artifacts written to /out. The container
        is always destroyed, even on timeout.

        on_line(stream, line) - if provided, called for each output line as it
        is produced ("stdout"/"stderr").
        """
        self.ensure_image()

        timeout = timeout or _env_int("SANDBOX_TIMEOUT", 30)
        memory = memory or os.getenv("SANDBOX_MEMORY", "512m")
        cpu = float(os.getenv("SANDBOX_CPU", "0.5")) if cpu is None else cpu
        output_cap = output_cap or _env_int("SANDBOX_OUTPUT_CAP", 32_768)
        total_artifact_cap = _env_int("SANDBOX_ARTIFACT_CAP", 1_000_000)

        tmp = self._prepare_workdir(code, input_files or {})
        streams: Dict[str, List[str]] = {"stdout": [], "stderr": []}

        def _append(stream: str, text: str) -> None:
            streams[stream].append(text)
            if on_line:
                for line in text.splitlines():
                    on_line(stream, line)
            joined = "".join(streams[stream])
            if len(joined) > output_cap:
                # Keep only the tail - the beginning of a huge dump is useless
                streams[stream] = [joined[-output_cap:]]

        def _reader(container, stream: str, stdout: bool):
            try:
                for chunk in container.logs(stdout=stdout, stderr=not stdout, stream=True, follow=True):
                    _append(stream, chunk.decode("utf-8", "replace"))
            except Exception:
                pass  # container removed under us - fine

        warnings: List[str] = []
        timed_out = False
        exit_code: Optional[int] = None

        container = self.client.containers.run(
            image=self.image,
            command=["python", "/main.py"],
            detach=True,
            network_mode="none",  # THE critical line: generated code has no network
            read_only=True,
            tmpfs={"/tmp": "size=64m"},
            volumes=[
                f"{tmp}/main.py:/main.py:ro",
                f"{tmp}/in:/in:ro",
                f"{tmp}/out:/out:rw",
            ],
            mem_limit=memory,
            cpu_quota=int(cpu * 100000),
            cpu_period=100000,
            labels={"agent-sandbox": "ephemeral"},
        )

        readers = [
            threading.Thread(target=_reader, args=(container, "stdout", True), daemon=True),
            threading.Thread(target=_reader, args=(container, "stderr", False), daemon=True),
        ]
        for r in readers:
            r.start()

        start = time.time()
        try:
            wait_result = container.wait(timeout=timeout)
            exit_code = wait_result.get("StatusCode")
        except Exception:
            # wall-clock timeout (or docker error): kill, then grab final status
            timed_out = True
            try:
                container.kill()
            except Exception:
                pass
            try:
                wait_result = container.wait(timeout=5)
                exit_code = wait_result.get("StatusCode") if wait_result else None
            except Exception:
                exit_code = None

        for r in readers:
            r.join(timeout=10.0)

        # Fallback: if streaming captured nothing (e.g. killed before EOF),
        # pull the final logs once more.
        if not "".join(streams["stdout"]).strip() and not "".join(streams["stderr"]).strip():
            try:
                out = container.logs(stdout=True, stderr=False).decode("utf-8", "replace")
                err = container.logs(stdout=False, stderr=True).decode("utf-8", "replace")
                streams["stdout"], streams["stderr"] = [out], [err]
            except Exception:
                pass

        stdout_text = "".join(streams["stdout"])
        stderr_text = "".join(streams["stderr"])
        tail_out, tail_err = stdout_text[-output_cap:], stderr_text[-output_cap:]
        if len(stdout_text) > output_cap:
            warnings.append(f"stdout truncated to {output_cap} bytes (tail kept)")
        if len(stderr_text) > output_cap:
            warnings.append(f"stderr truncated to {output_cap} bytes (tail kept)")

        artifacts = self._collect_artifacts(Path(tmp) / "out", total_artifact_cap)
        shutil.rmtree(tmp, ignore_errors=True)

        try:
            container.remove(force=True)
        except Exception:
            warnings.append("could not remove sandbox container (check docker daemon)")

        duration_ms = int((time.time() - start) * 1000)
        if timed_out:
            warnings.append(f"killed after {timeout}s wall-clock timeout")
        elif exit_code not in (0, None):
            warnings.append(f"non-zero exit code {exit_code}")

        return {
            "exit_code": exit_code,
            "timed_out": timed_out,
            "stdout": tail_out,
            "stderr": tail_err,
            "artifacts": artifacts,
            "warnings": warnings,
            "duration_ms": duration_ms,
        }

    async def run_code(self, *args, **kwargs) -> dict:
        """Async wrapper - the docker SDK is sync, so run it off the loop."""
        return await asyncio.to_thread(self.run_code_sync, *args, **kwargs)

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass


# ----------------------------------------------------------------------
# Module-level lazy singleton for the tools package
# ----------------------------------------------------------------------
_manager: Optional[SandboxManager] = None
_manager_lock = asyncio.Lock()


async def get_sandbox_manager() -> SandboxManager:
    global _manager
    async with _manager_lock:
        if _manager is None:
            _manager = SandboxManager()
        return _manager
