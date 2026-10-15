"""Gate a built APK on what Android will see: debuggable or not, application id, versionCode.

Tester builds (Codemagic) must never be debuggable; the owner build (gordon) must be, so adb can read its
database. Reads `aapt2 dump badging`, so it checks the packaged manifest, not the build configuration.
Stdlib only; prints reasons, never anything secret.

    check_apk.py app-release.apk --expect release [--version-code N]
"""

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

APPLICATION_ID = "com.ruaridhw.glean"
_PACKAGE = re.compile(r"^package: name='([^']*)' versionCode='(\d+)'", re.MULTILINE)
# aapt2 prints a bare `application-debuggable` line only for a debuggable APK.
_DEBUGGABLE = re.compile(r"^application-debuggable$", re.MULTILINE)


@dataclass(frozen=True)
class ApkFacts:
    package: str
    version_code: int
    debuggable: bool


def parse_badging(text: str) -> ApkFacts:
    match = _PACKAGE.search(text)
    if match is None:
        raise ValueError("no package line in aapt2 badging output")
    return ApkFacts(match.group(1), int(match.group(2)), bool(_DEBUGGABLE.search(text)))


def problems(facts: ApkFacts, *, expect: str, version_code: int | None = None) -> list[str]:
    found: list[str] = []
    if facts.package != APPLICATION_ID:
        found.append(f"application id is {facts.package}, expected {APPLICATION_ID}")
    if expect == "release" and facts.debuggable:
        found.append("APK is debuggable; tester builds must not be")
    if expect == "owner" and not facts.debuggable:
        found.append("APK is not debuggable; the owner build must be")
    if version_code is not None and facts.version_code != version_code:
        found.append(f"versionCode is {facts.version_code}, expected {version_code}")
    return found


def find_aapt2() -> str:
    sdk = os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME") or str(Path.home() / "Android/Sdk")
    candidates = sorted(Path(sdk).glob("build-tools/*/aapt2"), key=lambda p: [int(n) for n in re.findall(r"\d+", p.parent.name)])
    if not candidates:
        raise FileNotFoundError(f"no aapt2 under {sdk}/build-tools")
    return str(candidates[-1])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("apk")
    parser.add_argument("--expect", choices=("release", "owner"), required=True)
    parser.add_argument("--version-code", type=int)
    parser.add_argument("--aapt2", help="path to aapt2 (default: newest in the Android SDK)")
    args = parser.parse_args(argv)
    try:
        aapt2 = args.aapt2 or find_aapt2()
        output = subprocess.run([aapt2, "dump", "badging", args.apk], capture_output=True, text=True, check=True).stdout
        facts = parse_badging(output)
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"check_apk: could not read {args.apk}: {error}", file=sys.stderr)
        return 1
    found = problems(facts, expect=args.expect, version_code=args.version_code)
    for problem in found:
        print(f"check_apk: {problem}", file=sys.stderr)
    if not found:
        print(f"check_apk: ok ({facts.package} versionCode {facts.version_code}, debuggable={facts.debuggable})")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
