import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
EXAMPLE_ENV_PATH = _ROOT / "example.env"
DOTENV_PATH = _ROOT / ".env"

_ENV_VERSION_LINE = re.compile(r"^ENV_VERSION\s*=\s*(.*)$")


def read_version(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_VERSION_LINE.match(line)
        if match:
            value = match.group(1).strip().strip("'").strip('"')
            return value or None
    return None


def warn_if_env_outdated() -> None:
    expected = read_version(EXAMPLE_ENV_PATH)
    actual = read_version(DOTENV_PATH)

    if expected is None:
        print(
            "Warning: example.env has no ENV_VERSION. Cannot check if .env is up to date.",
            file=sys.stderr,
        )
        return

    if actual == expected:
        return

    actual_label = actual if actual else "none"
    print(
        f"Warning: .env version is {actual_label}, but example.env is {expected}.\n"
        "Copy any new keys from example.env into your .env, then set ENV_VERSION to match.\n"
        "See changelog.md for what changed.",
        file=sys.stderr,
    )
