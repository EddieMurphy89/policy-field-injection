"""Record model configuration and observable runtime settings without credentials."""

import importlib.metadata
import os
import platform
from pathlib import Path
from functools import lru_cache


@lru_cache(maxsize=1)
def package_versions():
    packages = {}
    for name in ("torch", "transformers", "mlx", "mlx-lm", "mlx-vlm", "laya"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return packages


def capture(backend, response=None):
    settings = {}
    prefixes = {"intern": "INTERN", "clef": "CLEF", "laya": "LAYA",
                "decider": "DECIDER", "jevstyle": "JEVSTYLE", "julia": "JULIA",
                "nanojev": "NANOJEV", "openjev4b": "OPENJEV4B",
                "openjev_deberta": "OPENJEV", "openthai": "OPENTHAI", "semif": "SEMIF"}
    prefix = prefixes.get(backend)
    if prefix:
        for suffix in ("DEVICE", "DTYPE", "REVISION"):
            value = os.environ.get(prefix + "_" + suffix)
            if value:
                settings[suffix.lower()] = value
        path = os.environ.get(prefix + ("_DIR" if backend == "openjev4b" else "_MODEL_DIR"))
        if not path:
            import sys
            module = sys.modules.get(f"clients.{backend}_client")
            resolver = getattr(module, "_model_dir", None)
            if callable(resolver):
                path = resolver()
        if path:
            settings["checkpoint"] = Path(path).name
            metadata = Path(path) / ".cache/huggingface/download/config.json.metadata"
            if metadata.is_file():
                settings["snapshot_revision"] = metadata.read_text().splitlines()[0]
    fixed = {"julia": ("cpu", "float32"), "nanojev": ("cpu", "float32"),
             "decider": (os.environ.get("DECIDER_DEVICE", "cpu"), "float32"),
             "intern": (os.environ.get("INTERN_DEVICE", "cpu"), os.environ.get("INTERN_DTYPE", "float32")),
             "clef": ("mlx", "4-bit checkpoint"),
             "semif": ("mlx", "bfloat16"),
             "jev": ("provider-managed", "provider-managed")}
    if backend in fixed:
        settings.setdefault("device", fixed[backend][0])
        settings.setdefault("precision", fixed[backend][1])
    if "dtype" in settings:
        settings.setdefault("precision", settings["dtype"])
    settings.setdefault("device", "not exposed by adapter")
    settings.setdefault("precision", "not exposed by adapter")
    if response and "@" in str(response.get("model", "")):
        settings.setdefault("model_revision", response["model"].rsplit("@", 1)[1])
    settings["settings_source"] = "adapter configuration"
    # Prefer tensor observations after the model has loaded.
    import sys
    module = sys.modules.get(f"clients.{backend}_client")
    if backend == "semif" and module and getattr(module, "_CACHE", None):
        metadata = module._CACHE[2]
        settings.update(precision=metadata.get("dtype", settings["precision"]),
                        snapshot_revision=metadata["revision"],
                        prompt_version="direct-options-v1",
                        settings_source="loaded SemIf model metadata")
    if module:
        for key in ("_ENGINE", "_MODEL", "_CACHE", "_AGENT", "_DECIDER", "_CLIENT"):
            obj = getattr(module, key, None)
            if isinstance(obj, tuple):
                obj = obj[0]
            obj = getattr(obj, "model", obj)
            try:
                parameter = next(obj.parameters())
                settings.update(device=str(parameter.device), precision=str(parameter.dtype),
                                settings_source="loaded tensor")
                break
            except (AttributeError, StopIteration, TypeError):
                continue
    return {"backend": backend, "model": (response or {}).get("model"),
            "python": platform.python_version(), "execution": settings, "packages": package_versions()}


def detector_settings():
    return {"backend": "intern", "checkpoint": "Intern-Decision-2B",
            "device": os.environ.get("DETECTOR_DEVICE", "cpu"),
            "precision": os.environ.get("DETECTOR_DTYPE", "float32"),
            "revision": "8797836c65fc91a2435b1fb6850b5f0aabd75cc3",
            "settings_source": "detector configuration"}
