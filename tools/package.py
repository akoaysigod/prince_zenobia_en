"""Package a release: build/ogre_battle_en_patch.zip with the IPS patch, the release readme
and the font licence (CC BY-SA 4.0 requires the licence to travel with the font).

Run after a build: python3 tools/package.py
"""
import os
import sys
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
FILES = {  # name in the zip: path in the project
    'ogre_battle_en.ips': 'build/ogre_battle_en.ips',
    'README.txt': 'release/README.txt',
    'FONT-LICENSE.txt': 'tools/fonts/LICENSE.TXT',
}
OUT = os.path.join(ROOT, 'build', 'ogre_battle_en_patch.zip')


def main():
    missing = [p for p in FILES.values() if not os.path.exists(os.path.join(ROOT, p))]
    if missing:
        sys.exit(f"missing: {', '.join(missing)} (build the patch first)")
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, path in FILES.items():
            z.write(os.path.join(ROOT, path), name)
    print(f'wrote {os.path.normpath(OUT)}')


if __name__ == '__main__':
    main()
