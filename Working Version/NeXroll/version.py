#!/usr/bin/env python3
"""
Version management script for NeXroll.
Reads version from package.json and provides version information for builds.
"""

import json
import os
import sys
from pathlib import Path

def get_version():
    """Get version from package.json"""
    try:
        # If running as a frozen executable (PyInstaller), prefer the installer-installed
        # frontend package.json next to the executable, then the extracted _MEIPASS copy.
        try:
            import sys as _sys
            if getattr(_sys, 'frozen', False):
                # install root (where the exe lives)
                try:
                    exe_dir = Path(_sys.executable).parent
                    inst_pkg = exe_dir / 'frontend' / 'package.json'
                    if inst_pkg.exists():
                        with open(inst_pkg, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            return data.get('version', '1.0.0')
                except Exception:
                    pass

                # PyInstaller _MEIPASS resource dir
                try:
                    meipass = getattr(_sys, '_MEIPASS', None)
                    if meipass:
                        res_pkg = Path(meipass) / 'frontend' / 'package.json'
                        if res_pkg.exists():
                            with open(res_pkg, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                return data.get('version', '1.0.0')
                except Exception:
                    pass
        except Exception:
            pass
        # Try frontend package.json (source tree) first
        frontend_package = Path(__file__).parent / "frontend" / "package.json"
        if frontend_package.exists():
            with open(frontend_package, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('version', '1.0.0')

        # Fallback to root package.json if it exists
        root_package = Path(__file__).parent / "package.json"
        if root_package.exists():
            with open(root_package, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('version', '1.0.0')
    except Exception as e:
        print(f"Warning: Could not read version from package.json: {e}", file=sys.stderr)

    return '1.0.0'

def get_version_info():
    """Get comprehensive version information"""
    version = get_version()
    version_parts = version.split('.')
    # Pad to 4 parts for NSIS VIProductVersion format
    while len(version_parts) < 4:
        version_parts.append('0')

    return {
        'version': version,
        'version_dotted': version,  # Same as version for now
        'version_comma': '.'.join(version_parts),  # For NSIS VIProductVersion (dots, not commas)
        'publisher': 'JFLXCLOUD',
        'product_name': 'NeXroll',
        'copyright': '© 2025 JFLXCLOUD'
    }

def write_nsis_version_header(output_file=None):
    """Write NSIS version header file"""
    info = get_version_info()

    content = f'''!define APP_VERSION "{info['version']}"
VIProductVersion "{info['version_comma']}.0"
VIAddVersionKey /LANG=1033 "ProductName" "{info['product_name']}"
VIAddVersionKey /LANG=1033 "ProductVersion" "{info['version']}"
VIAddVersionKey /LANG=1033 "FileVersion" "{info['version']}"
VIAddVersionKey /LANG=1033 "CompanyName" "{info['publisher']}"
VIAddVersionKey /LANG=1033 "FileDescription" "{info['product_name']} Installer"
VIAddVersionKey /LANG=1033 "LegalCopyright" "{info['copyright']}"
'''

    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"NSIS version header written to: {output_file}")
    else:
        print(content)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--nsis":
        write_nsis_version_header()
    else:
        info = get_version_info()
        print(f"Version: {info['version']}")
        print(f"Publisher: {info['publisher']}")
        print(f"Product: {info['product_name']}")

def update_installer_nsi():
    """Update the installer.nsi file with current version information"""
    info = get_version_info()

    nsis_file = Path(__file__).parent / "installer.nsi"
    if not nsis_file.exists():
        print(f"installer.nsi not found at {nsis_file}")
        return False

    try:
        with open(nsis_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Update version define
        old_version = '!define APP_VERSION "1.5.0"'
        new_version = f'!define APP_VERSION "{info["version"]}"'
        if old_version in content:
            content = content.replace(old_version, new_version)

        # Update VIProductVersion
        old_vi = 'VIProductVersion "1.5.0.0"'
        new_vi = f'VIProductVersion "{info["version_comma"]}.0"'
        if old_vi in content:
            content = content.replace(old_vi, new_vi)

        # Update version keys
        old_product_version = 'VIAddVersionKey /LANG=1033 "ProductVersion" "1.5.0"'
        new_product_version = f'VIAddVersionKey /LANG=1033 "ProductVersion" "{info["version"]}"'
        if old_product_version in content:
            content = content.replace(old_product_version, new_product_version)

        old_file_version = 'VIAddVersionKey /LANG=1033 "FileVersion" "1.5.0"'
        new_file_version = f'VIAddVersionKey /LANG=1033 "FileVersion" "{info["version"]}"'
        if old_file_version in content:
            content = content.replace(old_file_version, new_file_version)

        # Update output filename
        old_outfile = 'OutFile "NeXroll_Installer_1.5.0.exe"'
        new_outfile = f'OutFile "NeXroll_Installer_{info["version"]}.exe"'
        if old_outfile in content:
            content = content.replace(old_outfile, new_outfile)

        # Update display version in uninstall registry
        old_display_version = 'WriteRegStr HKLM "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Uninstall\\\\NeXroll" "DisplayVersion" "1.5.0"'
        new_display_version = f'WriteRegStr HKLM "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Uninstall\\\\NeXroll" "DisplayVersion" "{info["version"]}"'
        if old_display_version in content:
            content = content.replace(old_display_version, new_display_version)

        # Update version in registry
        old_reg_version = 'WriteRegStr HKLM "Software\\\\NeXroll" "Version" "1.5.0"'
        new_reg_version = f'WriteRegStr HKLM "Software\\\\NeXroll" "Version" "{info["version"]}"'
        if old_reg_version in content:
            content = content.replace(old_reg_version, new_reg_version)

        with open(nsis_file, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"Updated installer.nsi with version {info['version']}")
        return True

    except Exception as e:
        print(f"Error updating installer.nsi: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--update-installer":
        update_installer_nsi()
    elif len(sys.argv) > 1 and sys.argv[1] == "--nsis":
        write_nsis_version_header()
    else:
        info = get_version_info()
        print(f"Version: {info['version']}")
        print(f"Publisher: {info['publisher']}")
        print(f"Product: {info['product_name']}")
        print("Use --update-installer to update installer.nsi")
        print("Use --nsis to generate NSIS header")