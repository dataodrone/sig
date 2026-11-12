import os
import subprocess
import sys

PYPI_PACKAGES = [
    "segment-anything",
    "open-clip-torch",
    "opencv-python-headless",
    "pillow",
    "numpy",
]


def deps_dir(plugin_dir):
    return os.path.join(plugin_dir, ".deps")


def deps_ready(plugin_dir):
    return os.path.isdir(os.path.join(deps_dir(plugin_dir), "segment_anything"))


def add_deps_to_path(plugin_dir):
    target = deps_dir(plugin_dir)
    if os.path.isdir(target) and target not in sys.path:
        sys.path.insert(0, target)


def ensure_deps(plugin_dir, progress=None):
    """Install the local AI stack into <plugin>/.deps on first run.

    Everything comes from free, public sources (PyPI and the PyTorch CPU
    index). No account, no API key, no subscription is involved.
    """
    report = progress or (lambda _msg: None)
    target = deps_dir(plugin_dir)
    if deps_ready(plugin_dir):
        add_deps_to_path(plugin_dir)
        return target
    os.makedirs(target, exist_ok=True)
    report("Installing PyTorch (CPU) into the plugin folder, first run only...")
    _pip([
        sys.executable, "-m", "pip", "install",
        "--disable-pip-version-check", "--quiet",
        "--index-url", "https://download.pytorch.org/whl/cpu",
        "--target", target, "torch",
    ])
    report("Installing segmentation and CLIP libraries (free, open source)...")
    _pip([
        sys.executable, "-m", "pip", "install",
        "--disable-pip-version-check", "--quiet",
        "--target", target,
    ] + PYPI_PACKAGES)
    add_deps_to_path(plugin_dir)
    return target


def _pip(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-2000:]
        raise RuntimeError("pip install failed:\n" + tail)
