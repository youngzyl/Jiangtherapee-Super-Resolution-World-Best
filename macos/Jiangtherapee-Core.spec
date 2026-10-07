from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

root = Path(SPECPATH).parent
wgpu_data = collect_data_files('wgpu')
wgpu_binaries = collect_dynamic_libs('wgpu')
licenses = []
for package in ('wgpu', 'numpy', 'opencv-python', 'cffi', 'pycparser',
                'pyobjc-core', 'pyobjc-framework-Cocoa', 'rendercanvas'):
    licenses += copy_metadata(package)
a = Analysis(
    [str(root / 'macos' / 'core_app.py')],
    pathex=[str(root / 'Core-Only-Source-Code')],
    binaries=wgpu_binaries,
    datas=wgpu_data + licenses + [
        (str(root / 'Core-Only-Source-Code' / 'weights'), 'weights'),
        (str(root / 'docs' / 'macos.md'), 'docs'),
    ],
    hiddenimports=['wgpu.backends.wgpu_native', 'AppKit', 'Foundation', 'wgpu_unet_tiled', 'wgpu_net'],
    hookspath=[], runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Jiangtherapee-Core',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, target_arch='arm64', codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Jiangtherapee-Core')
app = BUNDLE(coll, name='Jiangtherapee Core.app', icon=None,
             bundle_identifier='io.github.youngzyl.jiangtherapee-core',
             info_plist={'CFBundleShortVersionString': '0.1.0',
                         'NSHighResolutionCapable': True,
                         'LSMinimumSystemVersion': '14.0'})
