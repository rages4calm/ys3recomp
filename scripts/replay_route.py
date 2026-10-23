"""Reproduce a private frozen route through the upstream TCP client.

No game files, generated code, frames, or saves are copied. All retained output
is confined to the explicitly selected new directory. This is an internal
reproducibility check, not an independent console oracle.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
import tomllib

if __package__:
    from .audio_contract import audio_command, extract_audio, without_audio
    from .desktop_contract import (desktop_audio, desktop_command, headless_status,
                                   validate_desktop, validate_desktop_mode)
else:
    from audio_contract import audio_command, extract_audio, without_audio
    from desktop_contract import (desktop_audio, desktop_command, headless_status,
                                  validate_desktop, validate_desktop_mode)

MAX_ROUTE_BYTES = 4 * 1024 * 1024
MAX_LOG_BYTES = 4 * 1024 * 1024
PHASE_SECONDS = 1800
STATUS_FIELDS = ("frame", "ticks", "paused", "local_paused", "host")


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def require_integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{label} must be an integer in {low}..{high}")


def command_value(command, name):
    if command.count(name) != 1 or command.index(name) + 1 == len(command):
        raise ValueError(f"command requires one value for {name}")
    return command[command.index(name) + 1]


def validate_route(route):
    """Validate bounded steps before permitting any child execution."""
    command = route["initial_command"]
    if not isinstance(command, list) or len(command) < 8 or not all(
            isinstance(value, str) and value and "\0" not in value for value in command):
        raise ValueError("invalid initial command")
    if any(flag in command for flag in ("--frame-out", "--window-capture", "--wall-seconds",
                                        "--audio-out", "--audio-frames", "--audio-output")):
        raise ValueError("source command contains file output or a conflicting wall limit")
    if command_value(command, "--dev-start-paused") != "on":
        raise ValueError("source must start paused")
    command_value(command, "--bram")
    command_value(command, "--dev-port")
    writes = "--dev-memory-write" in command and command_value(command, "--dev-memory-write") == "on"
    status = route["last_status"]
    if status["paused"] is not True or status["host"]["cd_control"]["bram_seeded"] is not True:
        raise ValueError("source must finish paused with an explicit BRAM seed")
    frame = 0
    boundaries = {0}
    steps = route["steps"]
    if not isinstance(steps, list) or len(steps) > 100_000:
        raise ValueError("route exceeds step count bound")
    for step in steps:
        if "memory_write" in step:
            if not writes or type(step.get("frame")) is not int or step["frame"] != frame:
                raise ValueError("memory edit requires explicit opt-in at its recorded paused frame")
            edit = step["memory_write"]
            require_integer(edit["address"], 0, 0x1FFFFF, "memory address")
            for key in ("data", "expected"):
                value = edit[key]
                if not isinstance(value, str) or not re.fullmatch(r"(?:[0-9a-f]{2}){1,256}", value):
                    raise ValueError("memory bytes require 1..256 lowercase hexadecimal bytes")
            if len(edit["data"]) != len(edit["expected"]) or edit["address"] + len(edit["data"]) // 2 > 0x200000:
                raise ValueError("memory edit range invalid")
        else:
            require_integer(step["frames"], 1, 600, "step frames")
            require_integer(step["mask"], 0, 4095, "input mask")
            require_integer(step["target_frame"], frame + step["frames"], (1 << 64) - 1, "target frame")
            frame = step["target_frame"]
            boundaries.add(frame)
    if frame != status["frame"]:
        raise ValueError("final status frame disagrees with complete route")
    checks = route["checkpoints"]
    if not isinstance(checks, list) or len(checks) > 10_000:
        raise ValueError("checkpoint count bound exceeded")
    for checkpoint in checks:
        require_integer(checkpoint["frame"], 0, frame, "checkpoint frame")
        if checkpoint["frame"] not in boundaries:
            raise ValueError("checkpoint is not at a paused route boundary")
        if not isinstance(checkpoint["file"], str) or not checkpoint["file"]:
            raise ValueError("checkpoint filename missing")
        if not isinstance(checkpoint["png_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", checkpoint["png_sha256"]):
            raise ValueError("invalid checkpoint hash")
    return boundaries


def project_status(status, ignore_tier_counters=False):
    """Keep every guest diagnostic; only transport metadata is unconditional."""
    result = copy.deepcopy({key: status[key] for key in STATUS_FIELDS})
    if ignore_tier_counters:
        for key in ("native_steps", "interpreter_steps"):
            result["host"].pop(key, None)
    return result


def compare_status(expected, actual, ignore_tier_counters=False, audio_mode=None, wav_limit=None,
                   desktop_packaged=False):
    left = project_status(expected, ignore_tier_counters)
    if desktop_packaged:
        actual = headless_status(actual, wav_limit)
    right = project_status(without_audio(actual, audio_mode, wav_limit) if audio_mode is not None else actual,
                           ignore_tier_counters)
    if left != right:
        changed = [key for key in STATUS_FIELDS if left[key] != right[key]]
        if "host" in changed:
            changed.extend("host." + key for key in sorted(set(left["host"]) | set(right["host"]))
                           if left["host"].get(key) != right["host"].get(key))
        raise RuntimeError("route status mismatch: " + ", ".join(changed))


def resolve_input(value, root):
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve(strict=True)


def source_binary_anchor(command, evidence_root, expected_hash, override=None):
    """Select an immutable historical executable without rewriting the route."""
    path = resolve_input(override if override is not None else command[0], evidence_root)
    if sha256(path) != expected_hash:
        raise ValueError("source binary identity mismatch")
    return path


def resolve_capture(checkpoint, route, route_path):
    roots = [route_path.parent]
    for value in (checkpoint.get("source_capture_root"), route.get("source_capture_root")):
        if value:
            roots.append(resolve_input(value, route_path.parent))
    for root in roots:
        path = root / checkpoint["file"]
        if path.is_file() and sha256(path) == checkpoint["png_sha256"]:
            return path.resolve()
    raise ValueError("retained checkpoint missing or changed: " + checkpoint["file"])


def verify_tool_root(tool_root, expected_revision=None):
    command = [sys.executable, str(Path(__file__).with_name("verify_tool.py")),
               "--tool-root", str(tool_root)]
    if expected_revision is not None:
        command += ["--expected-revision", expected_revision]
    verification = subprocess.run(
        command, check=True, capture_output=True, text=True, timeout=30)
    return json.loads(verification.stdout)


def upstream_client(tool_root, expected_revision=None):
    identity = verify_tool_root(tool_root, expected_revision)
    # Load the verified upstream implementation, without sharing its package
    # name with this consumer's own scripts namespace.
    source = tool_root / "scripts" / "dev_client.py"
    spec = importlib.util.spec_from_file_location("ys3_verified_upstream_dev_client", source)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module, identity


def unwrap_execution(value, expected_binary_hash=None, require_contract=False):
    """Accept only a qualified shared-contract envelope, or a direct runner."""
    if not isinstance(value, dict):
        raise ValueError("runner output must be a JSON object")
    if "kind" not in value and not require_contract:
        return value
    if value.get("kind") != "pce-consumer-execution" or value.get("qualified") is not True:
        raise ValueError("shared execution contract is missing or unqualified")
    if expected_binary_hash is not None and value.get("binary_sha256") != expected_binary_hash:
        raise ValueError("shared execution contract binary differs from selected target")
    if not isinstance(value.get("result"), dict):
        raise ValueError("shared execution contract has no runner result")
    return value["result"]


def validate_project_mode(descriptor, build, verify_only):
    if bool(descriptor) != bool(build):
        raise ValueError("project descriptor and project build must be supplied together")
    if verify_only and not descriptor:
        raise ValueError("project verify-only requires both descriptor and build")


def validate_project_binding(built, verification):
    """Bind an official verification result to its recorded official build."""
    if built.get("schema") != 1 or built.get("kind") != "pce-consumer-build":
        raise ValueError("shared build receipt schema/kind mismatch")
    if verification.get("schema") != 1 or verification.get("verified") is not True:
        raise ValueError("shared project verification did not succeed")
    binding = built.get("binding")
    if not isinstance(binding, dict) or set(verification) != set(binding) | {"schema", "verified"}:
        raise ValueError("shared verification/build binding fields differ")
    for key, expected in binding.items():
        # Canonical JSON comparison also distinguishes bools from integers.
        if json.dumps(verification[key], sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise ValueError("shared verification/build binding mismatch: " + key)
    return binding


def validate_project_outputs(built, binary):
    """Check selected binary and exact adjacent output set from build receipt."""
    if Path(built["binary"]).resolve(strict=True) != binary.resolve(strict=True) or sha256(binary) != built["binary_sha256"]:
        raise ValueError("selected target does not match shared build receipt binary")
    outputs = {path.name: sha256(path) for path in sorted(binary.parent.iterdir()) if path.is_file()}
    if outputs != built["output_files"]:
        raise ValueError("shared build output/dependency identities changed")
    return outputs


def verify_project_cli(descriptor, environment, cwd):
    """Delegate source/module/input identity algorithms to the shared toolkit."""
    completed = subprocess.run([sys.executable, "-m", "pcerecomp.project", "verify", str(descriptor)],
                               cwd=cwd, env=environment, check=True, capture_output=True,
                               text=True, timeout=60)
    if len(completed.stdout.encode("utf-8")) > MAX_ROUTE_BYTES:
        raise ValueError("shared verification result exceeds four-MiB bound")
    return json.loads(completed.stdout)


class BoundedChild:
    """One bounded child, with byte-capped logs and an independent watchdog."""
    def __init__(self, command, cwd, out, env=None, process_tree=False):
        self.deadline = time.monotonic() + PHASE_SECONDS
        self.lock = threading.Lock()
        self.log_bytes = 0
        self.failure = None
        self.port = None
        self.ready = threading.Event()
        self.done = threading.Event()
        self.process_tree = process_tree
        self.outputs = [(out / name).open("xb") for name in ("run.stdout", "run.stderr")]
        try:
            self.process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            env=env, start_new_session=process_tree and os.name != "nt",
                                            creationflags=0x08000000 if os.name == "nt" else 0)
        except BaseException:
            for output in self.outputs:
                output.close()
            raise
        self.readers = [threading.Thread(target=self._read, args=(index, stream), daemon=True)
                        for index, stream in enumerate((self.process.stdout, self.process.stderr))]
        for reader in self.readers:
            reader.start()
        self.watchdog = threading.Thread(target=self._watch, daemon=True)
        self.watchdog.start()

    def _read(self, index, stream):
        startup = bytearray()
        try:
            while block := stream.read1(4096):
                with self.lock:
                    room = max(0, MAX_LOG_BYTES - self.log_bytes)
                    self.outputs[index].write(block[:room])
                    self.outputs[index].flush()
                    self.log_bytes += min(room, len(block))
                    if len(block) > room:
                        self.failure = "combined log limit exceeded"
                if index == 1 and self.port is None:
                    startup.extend(block)
                    while b"\n" in startup:
                        line, _, remainder = startup.partition(b"\n")
                        startup = bytearray(remainder)
                        match = re.fullmatch(rb"PCE_DEV_PORT=([0-9]+)\r?", line)
                        if match:
                            port = int(match[1])
                            if not 1 <= port <= 65535:
                                raise ValueError("invalid development port")
                            self.port = port
                            self.ready.set()
                    if len(startup) > 8192:
                        raise ValueError("startup line exceeds bound")
        except BaseException as error:
            self.failure = "log reader: " + repr(error)
        finally:
            stream.close()

    def _watch(self):
        while not self.done.wait(0.1):
            if self.process.poll() is not None:
                return
            if time.monotonic() >= self.deadline:
                self.failure = "1800-second phase limit exceeded"
            if self.failure:
                self.stop()
                return

    def stop(self):
        if self.process.poll() is None:
            if self.process_tree and os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            elif self.process_tree:
                os.killpg(self.process.pid, signal.SIGTERM)
            else:
                self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def close(self):
        self.stop()
        self.done.set()
        self.watchdog.join(timeout=6)
        for reader in self.readers:
            reader.join(timeout=6)
        for output in self.outputs:
            output.close()


def replay(args):
    out = Path(args.out).resolve()
    if out.exists():
        raise ValueError("output directory must be new")
    evidence = Path(args.evidence_root).resolve(strict=True)
    tool = Path(args.tool_root).resolve(strict=True)
    if out.is_relative_to(evidence) or out.is_relative_to(tool):
        raise ValueError("output must be outside the read-only evidence and tool roots")
    out.mkdir(parents=True)
    receipt = {"passed": False, "phase_seconds_limit": PHASE_SECONDS,
               "combined_log_bytes_limit": MAX_LOG_BYTES, "retained_new_pngs": 0,
               "ignore_tier_counters": args.ignore_tier_counters, "images": [],
               "memory_edits_replayed": 0, "checkpoint_status": []}
    child = None
    started = time.monotonic()
    try:
        validate_project_mode(args.project_descriptor, args.project_build, args.project_verify_only)
        desktop_packaged = getattr(args, "desktop_packaged", False)
        validate_desktop_mode(desktop_packaged, args.project_verify_only, args.project_descriptor,
                              args.audio_output, args.audio_frames)
        if args.audio_output is not None and args.project_descriptor and not args.project_verify_only:
            raise ValueError("explicit audio route overrides require project verify-only supervision")
        client_module, tool_identity = upstream_client(tool, args.expected_revision)
        receipt["tool_identity"] = tool_identity
        route_path = Path(args.route).resolve(strict=True)
        if route_path.stat().st_size > MAX_ROUTE_BYTES:
            raise ValueError("route exceeds four-MiB bound")
        raw = route_path.read_bytes()
        route = json.loads(raw)
        validate_route(route)
        command = route["initial_command"].copy()
        source_binary = source_binary_anchor(command, evidence, route["binary_sha256"], args.source_binary)
        binary = Path(args.binary).resolve(strict=True)
        bram = resolve_input(command_value(command, "--bram"), evidence)
        if bram.stat().st_size != 2048 or sha256(bram) != route["initial_bram_sha256"]:
            raise ValueError("initial BRAM identity mismatch")
        identities = {str(route_path): hashlib.sha256(raw).hexdigest(),
                      str(source_binary): route["binary_sha256"], str(binary): sha256(binary),
                      str(bram): route["initial_bram_sha256"]}
        # Keep all original arguments and their relative-path resolution.
        # These are the upstream runner's file-reading arguments.
        for value in [command[1]] + [command_value(command, flag) for flag in
                                     ("--bios", "--toc", "--disc", "--libchdr", "--input-script")
                                     if flag in command]:
            path = resolve_input(value, evidence)
            identities[str(path)] = sha256(path)
        checks = {}
        for checkpoint in route["checkpoints"]:
            path = resolve_capture(checkpoint, route, route_path)
            identities[str(path)] = checkpoint["png_sha256"]
            checks.setdefault(checkpoint["frame"], []).append(checkpoint)
        command[0] = str(binary)
        if desktop_packaged:
            command = desktop_command(command, evidence)
        command = audio_command(command, args.audio_output, out / "audio.wav", args.audio_frames)
        receipt.update(command=command, source_command=route["initial_command"],
                       source_binary_anchor=str(source_binary),
                       source_binary_override=str(source_binary) if args.source_binary is not None else None,
                       source_route=str(route_path),
                       source_route_sha256=identities[str(route_path)],
                       input_sha256=identities, source_binary_sha256=route["binary_sha256"],
                       binary_sha256=identities[str(binary)], initial_bram_sha256=route["initial_bram_sha256"])
        if args.audio_output is not None:
            receipt["audio_contract"] = {"runtime_abi": 13, "mode": args.audio_output,
                                         "wav_frame_limit": args.audio_frames,
                                         "headless_pcm_only": not desktop_packaged,
                                         "scope": "PCM generation; no physical playback or independent mixed-audio parity claim."}
        launch_command = command
        environment = None
        contract_path = None
        project_guard_inputs = {}
        launch_cwd = evidence
        if args.project_descriptor:
            descriptor = Path(args.project_descriptor).resolve(strict=True)
            project_build = Path(args.project_build).resolve(strict=True)
            built = json.loads((project_build / "build-receipt.json").read_text(encoding="utf-8"))
            if Path(built["binary"]).resolve(strict=True) != binary or built["binary_sha256"] != identities[str(binary)]:
                raise ValueError("selected target does not match shared build receipt binary")
            environment = os.environ.copy()
            # The evidence cwd may itself contain a different pcerecomp checkout.
            # Suppress Python's implicit cwd import entry so the verified root
            # supplied through PYTHONPATH owns the shared contract implementation.
            environment.update(PYTHONPATH=str(tool), PYTHONDONTWRITEBYTECODE="1", PYTHONSAFEPATH="1")
            receipt.update(project_descriptor=str(descriptor), project_build=str(project_build),
                           project_descriptor_sha256=sha256(descriptor),
                           project_build_receipt_sha256=sha256(project_build / "build-receipt.json"))
            if args.project_verify_only:
                verification = verify_project_cli(descriptor, environment, evidence)
                binding = validate_project_binding(built, verification)
                output_hashes = validate_project_outputs(built, binary)
                declared_wall = tomllib.loads(descriptor.read_text(encoding="utf-8"))["limits"]["wall_seconds"]
                project_guard_inputs = {descriptor: receipt["project_descriptor_sha256"],
                                        project_build / "build-receipt.json": receipt["project_build_receipt_sha256"]}
                receipt.update(project_execution_mode="shared-verify-then-consumer-route",
                               shared_project_run_used=False, project_binding=binding,
                               project_verification_before=verification,
                               project_output_files_before=output_hashes,
                               host_bound_override={"explicit_project_verify_only": True,
                                                    "descriptor_wall_seconds": declared_wall,
                                                    "descriptor_wall_applied": False,
                                                    "effective_consumer_phase_seconds": PHASE_SECONDS,
                                                    "original_route_guest_arguments_preserved": True,
                                                    "explicit_audio_override": args.audio_output,
                                                    "scope": "Consumer TCP route watchdog; shared project.run was not used."})
            else:
                contract_path = out / "contract.json"
                launch_command = [sys.executable, "-m", "pcerecomp.project", "run", str(descriptor),
                                  "--build-dir", str(project_build), "--receipt", str(contract_path),
                                  "--dev-port", "0", "--start-paused", "--memory-write"]
        if desktop_packaged:
            if __package__:
                from .package_checks import packaged_environment, verify_package, inspect_loaded_sdl
            else:
                from package_checks import packaged_environment, verify_package, inspect_loaded_sdl
            package = verify_package(built, binary)
            environment, isolation = packaged_environment(binary, environment)
            launch_cwd = out / "cwd"
            launch_cwd.mkdir()
            receipt["desktop_contract"] = {"packaged": True, "package_before": package,
                                            "environment": isolation, "working_directory": str(launch_cwd),
                                            "working_directory_initially_empty": not any(launch_cwd.iterdir()),
                                            "hidden": True, "unthrottled": True,
                                            "scope": "Packaged SDL loading and fast-forward muted presentation; paced playback qualified separately."}
        receipt["launch_command"] = launch_command
        receipt["launch_cwd"] = str(launch_cwd)
        child = BoundedChild(launch_command, launch_cwd, out, env=environment, process_tree=contract_path is not None)
        until = time.monotonic() + 10
        while not child.ready.wait(0.05):
            if child.failure or child.process.poll() is not None or time.monotonic() >= until:
                raise RuntimeError("development TCP startup failed: " + str(child.failure))
        if desktop_packaged:
            receipt["desktop_contract"]["loaded_sdl_before"] = inspect_loaded_sdl(child.process.pid, binary.parent / "SDL3.dll")
        with client_module.DevClient(child.port, timeout=90) as client:
            def images(frame, status=None):
                if frame not in checks:
                    return
                metadata, rgb = client.capture("guest")
                receipt["checkpoint_status"].append(status if status is not None else client.call("status"))
                digest = hashlib.sha256(client_module.encode_png(metadata["width"], metadata["height"], rgb)).hexdigest()
                for checkpoint in checks[frame]:
                    if metadata["frame"] != frame or digest != checkpoint["png_sha256"]:
                        raise RuntimeError(f"guest image mismatch at frame {frame}")
                    receipt["images"].append({"frame": frame, "png_sha256": digest, "metadata": metadata})
            images(0)
            progress = 0
            for step in route["steps"]:
                if child.failure:
                    raise RuntimeError(child.failure)
                if "memory_write" in step:
                    edit = step["memory_write"]
                    client.write_memory(edit["address"], bytes.fromhex(edit["data"]), bytes.fromhex(edit["expected"]))
                    receipt["memory_edits_replayed"] += 1
                else:
                    client.call("set_input", mask=step["mask"])
                    status = client.advance(step["frames"])
                    receipt["last_completed_frame"] = status["frame"]
                    if status["frame"] != step["target_frame"]:
                        raise RuntimeError("frame advancement endpoint differs from route")
                    images(status["frame"], status)
                    if status["frame"] >= progress + 5000:
                        progress = status["frame"]
                        print(f"replay frame {progress}", flush=True)
            expected = route["last_status"]
            final = client.call("status")
            receipt["before_final_release"] = final
            if final["host"]["buttons"] != expected["host"]["buttons"]:
                if expected["host"]["buttons"] != [0] * 5:
                    raise RuntimeError("unrecorded nonzero final input")
                client.call("clear_input")
                released = client.call("status")
                cleared = copy.deepcopy(final)
                cleared["host"]["buttons"] = [0] * 5
                compare_status(cleared, released)
                final = released
            compare_status(expected, final, args.ignore_tier_counters, args.audio_output, args.audio_frames,
                           desktop_packaged=desktop_packaged)
            client.call("clear_input")
            released = client.call("status")
            cleared = copy.deepcopy(final)
            cleared["host"]["buttons"] = [0] * 5
            compare_status(cleared, released)
            receipt.update(final_status=final, released_status=released)
            if len(receipt["images"]) != len(route["checkpoints"]):
                raise RuntimeError("not every image checkpoint was compared")
            if desktop_packaged:
                receipt["desktop_contract"]["loaded_sdl_final"] = inspect_loaded_sdl(child.process.pid, binary.parent / "SDL3.dll")
            client.call("quit")
        child.process.wait(timeout=30 if contract_path is not None else 5)
        if child.process.returncode != 0 or child.failure:
            raise RuntimeError("child exit failed: " + str(child.failure))
        if contract_path is not None:
            # Wait for bounded stream readers before inspecting the wrapper's
            # sole final JSON. The shared runner owns descriptor/source guards.
            for reader in child.readers:
                reader.join(timeout=5)
            envelope = json.loads((out / "run.stdout").read_text(encoding="utf-8"))
            unwrap_execution(envelope, identities[str(binary)], require_contract=True)
            if json.loads(contract_path.read_text(encoding="utf-8")) != envelope:
                raise RuntimeError("shared receipt differs from wrapper stdout")
            receipt.update(contract_path=str(contract_path), contract_sha256=sha256(contract_path),
                           contract_command=envelope["command"], contract_binding=envelope.get("binding"))
        if args.audio_output is not None:
            for reader in child.readers:
                reader.join(timeout=5)
            runner = unwrap_execution(json.loads((out / "run.stdout").read_text(encoding="utf-8")))
            if desktop_packaged:
                audio = desktop_audio(runner["audio_output"], args.audio_frames)
                final_audio = desktop_audio(final["host"]["audio_output"], args.audio_frames)
                released_audio = desktop_audio(released["host"]["audio_output"], args.audio_frames)
                presentation = validate_desktop(runner["desktop"], final["frame"])
                receipt["desktop_contract"].update(audio_output=runner["audio_output"], presentation=presentation,
                                                    package_after=verify_package(built, binary),
                                                    working_directory_finally_empty=not any(launch_cwd.iterdir()))
                if any(launch_cwd.iterdir()):
                    raise RuntimeError("packaged replay wrote unexpected working-directory output")
            else:
                audio = extract_audio(copy.deepcopy(runner), args.audio_output, args.audio_frames)
                final_audio = extract_audio(copy.deepcopy(final["host"]), args.audio_output, args.audio_frames)
                released_audio = extract_audio(copy.deepcopy(released["host"]), args.audio_output, args.audio_frames)
            if audio != final_audio or audio != released_audio:
                raise RuntimeError("PCM diagnostics changed between paused guest status and clean exit")
            receipt["audio_contract"]["validated_output"] = audio
            receipt["audio_contract"]["audio_output_absent"] = args.audio_output == "off"
            if args.audio_frames is not None:
                wave_path = out / "audio.wav"
                import wave
                with wave.open(str(wave_path), "rb") as wave_input:
                    if (wave_input.getnchannels(), wave_input.getsampwidth(), wave_input.getframerate(),
                            wave_input.getnframes()) != (2, 2, 44100, audio["wav_frames"]):
                        raise RuntimeError("WAV format/frame count disagrees with PCM diagnostics")
                if wave_path.stat().st_size != 44 + 4 * audio["wav_frames"]:
                    raise RuntimeError("WAV byte count differs from bounded PCM output")
                receipt["audio_contract"].update(wav_path=str(wave_path), wav_sha256=sha256(wave_path),
                                                  wav_bytes=wave_path.stat().st_size)
        for name, expected_hash in identities.items():
            if sha256(name) != expected_hash:
                raise RuntimeError("read-only input changed during replay: " + name)
        if args.project_verify_only:
            for path, expected_hash in project_guard_inputs.items():
                if sha256(path) != expected_hash:
                    raise RuntimeError("project descriptor/build receipt changed during replay: " + str(path))
            verification_after = verify_project_cli(descriptor, environment, evidence)
            validate_project_binding(built, verification_after)
            receipt.update(project_verification_after=verification_after,
                           project_output_files_after=validate_project_outputs(built, binary))
        final_tool_identity = verify_tool_root(tool, args.expected_revision)
        if final_tool_identity != tool_identity:
            raise RuntimeError("verified tool identity changed during replay")
        receipt["tool_identity_after"] = final_tool_identity
        receipt.update(passed=True, exit_code=0)
    except BaseException as error:
        receipt.update(passed=False, error=repr(error))
        raise
    finally:
        if child is not None:
            child.close()
            receipt.update(log_bytes=child.log_bytes, guard_reason=child.failure,
                           exit_code=child.process.returncode)
        receipt["elapsed_seconds"] = time.monotonic() - started
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("tool-root", "evidence-root", "route", "binary", "out"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--source-binary", help="immutable historical executable; must match the unchanged route binary hash")
    parser.add_argument("--expected-revision", help="explicit development tool revision; public manifest pin remains the default")
    parser.add_argument("--project-descriptor", help="verified shared consumer descriptor")
    parser.add_argument("--project-build", help="shared consumer build directory; requires --project-descriptor")
    parser.add_argument("--project-verify-only", action="store_true",
                        help="use shared project verify before/after and preserve the original route under the consumer 1800-second watchdog")
    parser.add_argument("--ignore-tier-counters", action="store_true",
                        help="compare all state except native_steps and interpreter_steps")
    parser.add_argument("--audio-output", choices=("off", "on"),
                        help="explicit ABI 13 headless PCM bridge/route; validate only its added audio_output separately")
    parser.add_argument("--audio-frames", type=int,
                        help="capture a new bounded replay-dir/audio.wav; requires audio on, 1..5292000 stereo frames")
    parser.add_argument("--desktop-packaged", action="store_true",
                        help="verify packaged SDL desktop output, isolated DLL search and original TCP route with muted fast-forward")
    args = parser.parse_args()
    result = replay(args)
    print(f"PASS: {len(result['images'])} image checkpoints; receipt: {Path(args.out).resolve() / 'receipt.json'}")


if __name__ == "__main__":
    main()
