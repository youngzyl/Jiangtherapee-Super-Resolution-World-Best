# macOS inference-core app

This is a wrapper around the published JSR v9.7 inference core. It is **not**
the Jiangtherapee Bridge v2.3.11 Windows application and does not implement
RAW decoding, burst registration, Tap accumulation, Controller-guided fusion,
LCA correction, or the Windows interface. Those application components are
absent from this repository. The supplied Controller is exercised by the
diagnostic check but cannot produce fused RGB without the missing stage.

The app runs the supplied RefineNet with WGPU's Metal backend on an Apple
Silicon Mac running macOS 14 or newer (the bundled NumPy wheel requires 14). It bundles Python, dependencies, and
all supplied model weights; no separate Python installation is required.
It uses an ad-hoc signature for local use, and has no Apple Developer ID
signature or notarization. Intel Macs are not supported by this build.

## Use

Open `Jiangtherapee Core.app`, choose **Open prepared input…**, select an input
`.npz` file, then choose the output location. The input archive must contain:

| Key | Type and shape | Meaning |
| --- | --- | --- |
| `learned` | finite, nonnegative float array, H × W × 3 | learned fused linear RGB |
| `legacy` | finite, nonnegative float array, H × W × 3 | conventional fused linear RGB |
| `k` | scalar integer, 1 through 14 | actual input burst frame count |

Both RGB arrays must already be fused, geometrically aligned, and in the same
sensor-linear intensity units expected by the upstream core. Supply the learned
RGB first and the legacy RGB second. Any LCA correction must already have been
applied identically to both. This app does not create these inputs from RAW files
and does not upsample them. Output has the same H × W size as the prepared arrays.
Use authentic prepared data from the upstream pipeline for photographic results.

The output archive contains `rgb` (H × W × 3 float32 sensor-linear RGB) and `k`.
No white balance, display transfer function, or tone mapping is applied.
The core computes full-frame inference; very large arrays can exceed GPU buffer
limits, which are reported as an error. Jobs run in the background while the
window remains responsive. The app cannot quit while processing.

**Check GPU and models** verifies all 14 weight routes against upstream hashes,
runs small Controller and RefineNet computations on Metal, and checks finite
output, zero preservation, and intensity-scale equivariance. This is a core
smoke test; it does not establish full RAW-burst reconstruction quality.

Command-line mode is available through the bundled executable:

```sh
"dist/Jiangtherapee Core.app/Contents/MacOS/Jiangtherapee-Core" --self-test
"dist/Jiangtherapee Core.app/Contents/MacOS/Jiangtherapee-Core" \
  --input prepared.npz --output refined.npz
```

## Rebuild

Run from the repository root on an Apple Silicon Mac:

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r macos/requirements-lock.txt
.venv/bin/python macos/core_app.py --self-test
PYINSTALLER_CONFIG_DIR="$PWD/build/pyinstaller-cache" .venv/bin/python -m PyInstaller \
  --clean --noconfirm macos/Jiangtherapee-Core.spec
codesign --verify --deep --strict "dist/Jiangtherapee Core.app"
"dist/Jiangtherapee Core.app/Contents/MacOS/Jiangtherapee-Core" --self-test
ditto -c -k --sequesterRsrc --keepParent "dist/Jiangtherapee Core.app" \
  dist/Jiangtherapee-Core-macOS-arm64.zip
```

The upstream repository does not grant a top-level license for the core or
weights. Third-party RAW-decoder notices explicitly do not grant rights to those
components. Build artifacts are for the user's local evaluation; this workflow
does not upload app binaries to a public release.
