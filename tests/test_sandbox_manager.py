"""SandboxManager tests with a fully mocked docker client - no daemon needed.

Verifies the security envelope (network off, read-only rootfs, ro inputs,
rw /out), timeout handling, artifact collection and the output cap.
"""

import base64
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.sandbox import SandboxManager


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class FakeContainer:
    """Mimics the docker Container interface the manager uses."""

    def __init__(self, run_kwargs, exit_code=0, fail_wait=False):
        self.run_kwargs = run_kwargs
        self._exit_code = exit_code
        self._fail_wait = fail_wait
        self.killed = 0
        self.removed = 0
        # Simulate the process "writing" an artifact into the host out-dir
        out_host = run_kwargs["volumes"][2].split(":")[0]
        Path(out_host, "chart.txt").write_text("artifact-bytes")

    def wait(self, timeout=None):
        if self._fail_wait:
            raise RuntimeError("wall-clock timeout")
        return {"StatusCode": self._exit_code}

    def kill(self):
        self.killed += 1

    def remove(self, force=False):
        self.removed += 1

    def logs(self, stdout=True, stderr=True, stream=False, follow=False):
        if stream:
            return iter([b"line one\nline two\n"])
        if stdout:
            return b"line one\nline two\n"
        if stderr:
            return b""
        return b""


class FakeDockerClient:
    """Configurable stand-in for docker.DockerClient()."""

    def __init__(self, exit_code=0, fail_wait=False):
        self._exit_code = exit_code
        self._fail_wait = fail_wait
        self.last_run_kwargs = None
        self.container = None
        self._images = SimpleNamespace(get=lambda name: SimpleNamespace())
        self.images = self._images

    def containers_run(self, **kwargs):
        self.last_run_kwargs = kwargs
        self.container = FakeContainer(kwargs, self._exit_code, self._fail_wait)
        return self.container


def make_manager(exit_code=0, fail_wait=False) -> tuple[SandboxManager, FakeDockerClient]:
    client = FakeDockerClient(exit_code=exit_code, fail_wait=fail_wait)
    m = SandboxManager.__new__(SandboxManager)  # skip __init__ - no real client
    m.client = SimpleNamespace(
        containers=SimpleNamespace(run=client.containers_run),
        images=client.images,
    )
    m.image = "agent-sandbox:latest"
    m.build_dir = Path("infra/sandbox-image")
    return m, client




# ---------------------------------------------------------------------------
# Security envelope
# ---------------------------------------------------------------------------
class TestRunKwargs:
    def test_network_off_read_only_ro_inputs(self):
        m, client = make_manager()
        m.run_code_sync("print(1)", timeout=5)

        kw = client.last_run_kwargs
        assert kw["network_mode"] == "none"
        assert kw["read_only"] is True
        assert kw["tmpfs"]["/tmp"].startswith("size=")
        vols = {v.split(":")[1]: v.split(":")[-1] for v in kw["volumes"]}
        assert vols["/main.py"] == "ro"
        assert vols["/in"] == "ro"
        assert vols["/out"] == "rw"

    def test_resource_caps(self):
        m, client = make_manager()
        m.run_code_sync("pass", memory="256m", cpu=0.25)
        kw = client.last_run_kwargs
        assert kw["mem_limit"] == "256m"
        assert kw["cpu_quota"] == 25000
        assert kw["cpu_period"] == 100000

    def test_container_is_destroyed_after_run(self):
        m, client = make_manager()
        m.run_code_sync("pass", timeout=5)
        assert client.container.removed == 1
        assert client.container.killed == 0


# ---------------------------------------------------------------------------
# Execution result
# ---------------------------------------------------------------------------
class TestResult:
    def test_success_shape(self):
        m, client = make_manager()
        res = m.run_code_sync("print('ok')", timeout=5)
        assert res["exit_code"] == 0
        assert res["timed_out"] is False
        assert "line one" in res["stdout"]
        assert res["duration_ms"] >= 0

    def test_artifact_from_out_dir(self):
        m, client = make_manager()
        res = m.run_code_sync("pass", timeout=5)
        art = next(a for a in res["artifacts"] if a["name"] == "chart.txt")
        assert base64.b64decode(art["content_b64"]) == b"artifact-bytes"

    def test_input_files_serialized_json_and_bytes(self):
        import shutil
        m, _ = make_manager()
        tmp = m._prepare_workdir(
            "pass",
            {"data.json": {"rows": [1, 2, 3]}, "raw.txt": b"hello", "notes.md": "text"},
        )
        try:
            assert json.loads((Path(tmp) / "in" / "data.json").read_text()) == {"rows": [1, 2, 3]}
            assert (Path(tmp) / "in" / "raw.txt").read_bytes() == b"hello"
            assert (Path(tmp) / "in" / "notes.md").read_text() == "text"
            assert (Path(tmp) / "main.py").read_text() == "pass"
            assert (Path(tmp) / "out").is_dir()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_path_traversal_rejected(self):
        m, _ = make_manager()
        with pytest.raises(ValueError):
            m.run_code_sync("pass", input_files={"../etc/passwd": "x"}, timeout=5)

    def test_timeout_kills_and_flags(self):
        m, client = make_manager(fail_wait=True)
        res = m.run_code_sync("import time; time.sleep(60)", timeout=2)
        assert res["timed_out"] is True
        assert client.container.killed >= 1
        assert client.container.removed == 1
        assert any("timeout" in w for w in res["warnings"])

    def test_nonzero_exit_warns(self):
        m, _ = make_manager(exit_code=1)
        res = m.run_code_sync("raise SystemExit(1)", timeout=5)
        assert res["exit_code"] == 1
        assert any("exit code 1" in w for w in res["warnings"])

    def test_output_cap_keeps_tail(self):
        m, _ = make_manager()
        res = m.run_code_sync("pass", timeout=5, output_cap=8)
        assert len(res["stdout"]) <= 8
        assert any("truncated" in w for w in res["warnings"])

    def test_on_line_callback_receives_streams(self):
        m, _ = make_manager()
        seen = []
        m.run_code_sync("pass", timeout=5, on_line=lambda s, line: seen.append((s, line)))
        assert ("stdout", "line one") in seen
        assert ("stdout", "line two") in seen


# ---------------------------------------------------------------------------
# ensure_image
# ---------------------------------------------------------------------------
class TestEnsureImage:
    def test_builds_when_missing(self):
        import docker.errors
        m, _ = make_manager()
        built = {}

        class _Images:
            def get(self, name):
                raise docker.errors.ImageNotFound("gone")

            def build(self, path, tag, rm=True):
                built["tag"] = tag
                return SimpleNamespace()

        m.client = SimpleNamespace(containers=m.client.containers, images=_Images())
        m.ensure_image()
        assert built.get("tag") == m.image

    def test_noop_when_present(self):
        m, _ = make_manager()
        m.ensure_image()  # fake images.get succeeds - no build attempted
