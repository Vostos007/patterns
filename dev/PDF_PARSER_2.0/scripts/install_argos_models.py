"""Install Argos Translate models for ru/en/fr bidirectional pairs."""
from __future__ import annotations

import argostranslate.package as package

PAIRS = [
    ("en", "ru"),
    ("ru", "en"),
    ("en", "fr"),
    ("fr", "en"),
    ("fr", "ru"),
    ("ru", "fr"),
]


def main() -> None:
    print("Updating Argos package index...")
    package.update_package_index()
    available = package.get_available_packages()

    for src, tgt in PAIRS:
        matches = [p for p in available if p.from_code == src and p.to_code == tgt]
        if not matches:
            print(f"[WARN] No Argos model found for {src}->{tgt}")
            continue
        pkg = matches[0]
        version = getattr(pkg, "version", "?")
        print(f"Installing {src}->{tgt} ({version}) ...")
        package.install_from_path(pkg.download())

    print("Done.")


if __name__ == "__main__":
    main()
