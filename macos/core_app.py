"""macOS wrapper for the published RefineNet core, not the private RAW app."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import threading

if not getattr(sys, "frozen", False):
    CORE_DIR = Path(__file__).resolve().parents[1] / "Core-Only-Source-Code"
    sys.path.insert(0, str(CORE_DIR))
os.environ.setdefault("WGPU_BACKEND_TYPE", "Metal")

import numpy as np
from local_v7_frontend import local_amplitude
from weights import weight_paths
from wgpu_greenfilm_rarm import GreenFiLMTiledRArm, load_weights
import wgpu_buf


def validate_input(learned, legacy, k):
    if isinstance(k, bool) or not isinstance(k, (int, np.integer)) or not 1 <= k <= 14:
        raise ValueError("Frame count must be an integer from 1 to 14.")
    learned = np.asarray(learned, dtype=np.float32)
    legacy = np.asarray(legacy, dtype=np.float32)
    if learned.ndim != 3 or learned.shape[-1] != 3 or learned.shape != legacy.shape:
        raise ValueError("learned and legacy must have the same H × W × 3 RGB shape.")
    if min(learned.shape[:2]) < 1:
        raise ValueError("RGB arrays must not be empty.")
    if not np.isfinite(learned).all() or not np.isfinite(legacy).all():
        raise ValueError("RGB arrays must contain only finite values.")
    if np.any(learned < 0) or np.any(legacy < 0):
        raise ValueError("RGB arrays must be nonnegative sensor-linear values.")
    return learned, legacy, int(k)


def refine(learned, legacy, k):
    learned, legacy, k = validate_input(learned, legacy, k)
    paths = weight_paths(k)
    model = GreenFiLMTiledRArm(load_weights(paths["refinenet"]))
    try:
        value = np.concatenate((learned, legacy), axis=2).transpose(2, 0, 1)
        result = model.factorized(value, local_amplitude(legacy), codes=(0,))
        if not np.isfinite(result).all():
            raise RuntimeError("GPU reconstruction produced non-finite values.")
        return np.ascontiguousarray(result.transpose(1, 2, 0))
    finally:
        model.close()


def process_file(source: Path, destination: Path):
    if source.resolve() == destination.resolve():
        raise ValueError("Choose an output file different from the input.")
    with np.load(source, allow_pickle=False) as data:
        if not {"learned", "legacy", "k"}.issubset(data.files):
            raise ValueError("Input must contain learned, legacy, and scalar integer k.")
        k = data["k"]
        if k.shape != () or k.dtype.kind not in "iu":
            raise ValueError("k must be a scalar integer frame count.")
        frame_count = int(k)
        result = refine(data["learned"], data["legacy"], frame_count)
    # Passing a file object prevents NumPy silently changing the selected name.
    with destination.open("wb") as stream:
        np.savez_compressed(stream, rgb=result, k=np.int32(frame_count))
    return result.shape


def self_test():
    from weights import load_npz
    from wgpu_unet_tiled import TiledUNet, validate_weights
    for k in range(1, 15):
        paths = weight_paths(k)
        validate_weights(load_npz(paths["controller"]))
        load_weights(paths["refinenet"])
    rng = np.random.default_rng(19)
    legacy = rng.uniform(0.05, 0.4, (8, 8, 3)).astype(np.float32)
    learned = legacy.copy()
    result = refine(learned, legacy, 4)
    scaled = refine(learned * 2, legacy * 2, 4)
    np.testing.assert_allclose(scaled, result * 2, rtol=2e-4, atol=2e-5)
    assert result.shape == legacy.shape and np.isfinite(result).all()
    zero = refine(np.zeros_like(legacy), np.zeros_like(legacy), 4)
    np.testing.assert_array_equal(zero, np.zeros_like(zero))
    # Exercise the published Controller separately; its RAW fusion stage is absent.
    controller = TiledUNet(load_npz(weight_paths(4)["controller"]))
    control = controller.forward(np.zeros((151, 8, 8), dtype=np.float32))
    assert control.shape == (36, 8, 8) and np.isfinite(control).all()
    return {"status": "passed", "adapter": wgpu_buf.info(), "weight_routes": 14,
            "checks": ["weight integrity", "Controller GPU inference", "RefineNet GPU inference",
                       "intensity scaling", "zero input"], "output_shape": list(result.shape)}


def launch_gui():
    import AppKit as AK
    from Foundation import NSObject

    class AppDelegate(NSObject):
        def applicationDidFinishLaunching_(self, notification):
            app = AK.NSApplication.sharedApplication()
            app.setActivationPolicy_(AK.NSApplicationActivationPolicyRegular)
            menu = AK.NSMenu.alloc().init()
            item = AK.NSMenuItem.alloc().init()
            submenu = AK.NSMenu.alloc().initWithTitle_("Jiangtherapee Core")
            submenu.addItemWithTitle_action_keyEquivalent_("Quit Jiangtherapee Core", "terminate:", "q")
            item.setSubmenu_(submenu)
            menu.addItem_(item)
            app.setMainMenu_(menu)
            style = AK.NSWindowStyleMaskTitled | AK.NSWindowStyleMaskClosable | AK.NSWindowStyleMaskMiniaturizable
            self.window = AK.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                ((0, 0), (650, 345)), style, AK.NSBackingStoreBuffered, False)
            self.window.setTitle_("Jiangtherapee Inference Core")
            self.window.center()
            self.window.setReleasedWhenClosed_(False)
            view = self.window.contentView()

            def label(text, rect, size):
                field = AK.NSTextField.labelWithString_(text)
                field.setFrame_(rect)
                field.setFont_(AK.NSFont.systemFontOfSize_(size))
                field.setLineBreakMode_(AK.NSLineBreakByWordWrapping)
                field.setMaximumNumberOfLines_(0)
                view.addSubview_(field)
                return field

            label("Jiangtherapee Inference Core", ((28, 282), (590, 35)), 25)
            label("Refine prepared linear RGB with the published JSR model on your Mac.",
                  ((28, 240), (590, 35)), 14)
            label("This core app requires a prepared .npz file containing learned and legacy RGB arrays, "
                  "plus the frame count k. Both arrays must already be aligned and fused.\n\n"
                  "RAW import and burst alignment are unavailable in the published source.",
                  ((28, 126), (590, 105)), 14)
            self.buttons = []
            for title, action, rect in (
                ("Open prepared input…", "openInput:", ((28, 73), (240, 36))),
                ("Check GPU and models", "checkGPU:", ((285, 73), (240, 36))),
            ):
                button = AK.NSButton.buttonWithTitle_target_action_(title, self, action)
                button.setFrame_(rect)
                button.setBezelStyle_(AK.NSBezelStyleRounded)
                view.addSubview_(button)
                self.buttons.append(button)
            self.status = label("Ready · Apple Silicon · Metal", ((28, 22), (590, 35)), 12)
            self.window.makeKeyAndOrderFront_(None)
            app.activateIgnoringOtherApps_(True)

        def applicationShouldTerminateAfterLastWindowClosed_(self, app):
            return True

        def applicationShouldTerminate_(self, app):
            if getattr(self, "busy", False):
                self.status.setStringValue_("Processing. Wait for the current job before quitting.")
                return AK.NSTerminateCancel
            return AK.NSTerminateNow

        def startJob_(self, job):
            self.busy = True
            for button in self.buttons:
                button.setEnabled_(False)
            self.status.setStringValue_("Processing on Metal…")

            def worker():
                try:
                    result = ("Completed", job())
                except Exception as exc:
                    result = ("Unable to complete", str(exc))
                self.performSelectorOnMainThread_withObject_waitUntilDone_("finishJob:", result, False)

            threading.Thread(target=worker, daemon=True).start()

        def finishJob_(self, result):
            self.busy = False
            for button in self.buttons:
                button.setEnabled_(True)
            self.status.setStringValue_(result[0])
            alert = AK.NSAlert.alloc().init()
            alert.setMessageText_(result[0])
            alert.setInformativeText_(result[1])
            alert.addButtonWithTitle_("OK")
            alert.runModal()

        def checkGPU_(self, sender):
            def job():
                result = self_test()
                adapter = result["adapter"]
                return f"All 14 model routes verified. GPU inference checks passed.\n\n{adapter.get('device', adapter)}"
            self.startJob_(job)

        def openInput_(self, sender):
            panel = AK.NSOpenPanel.openPanel()
            panel.setAllowedFileTypes_(["npz"])
            panel.setAllowsMultipleSelection_(False)
            if panel.runModal() != AK.NSModalResponseOK:
                return
            source = Path(panel.URL().path())
            save = AK.NSSavePanel.savePanel()
            save.setAllowedFileTypes_(["npz"])
            save.setNameFieldStringValue_(source.stem + "-refined.npz")
            if save.runModal() != AK.NSModalResponseOK:
                return
            destination = Path(save.URL().path())

            def job():
                shape = process_file(source, destination)
                return f"Saved linear RGB ({shape[1]} × {shape[0]}) to:\n{destination}"
            self.startJob_(job)

    app = AK.NSApplication.sharedApplication()
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2))
    elif args.input or args.output:
        if not args.input or not args.output:
            parser.error("--input and --output must be supplied together")
        print(json.dumps({"output": str(args.output), "shape": process_file(args.input, args.output)}))
    else:
        launch_gui()


if __name__ == "__main__":
    main()
