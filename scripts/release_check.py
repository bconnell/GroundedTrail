"""Local release hygiene audit. No external services or filesystem writes."""

from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".md", ".html", ".js", ".css", ".txt", ".toml", ".yaml", ".yml", ".json", ".example"}
EXCLUDED_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "dist", "build"}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "secret token": re.compile(r"(?:sk-proj-|ghp_|github_pat_)[A-Za-z0-9_-]{12,}"),
    "personal home directory": re.compile(r"(?:C:\\Users\\[^\\\s]+\\|/home/(?!appuser/)[^/\s]+/(?:Desktop|Documents|Downloads)/)"),
    "unresolved placeholder": re.compile(r"\b(?:TODO|FIXME|TBD):\b"),
}


def audit() -> list[str]:
    errors: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or any(part in EXCLUDED_DIRS for part in path.relative_to(ROOT).parts):
            continue
        relative = path.relative_to(ROOT)
        if path.name.startswith(".env") and path.name != ".env.example":
            errors.append(f"{relative}: local environment file must not be committed")
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"Dockerfile", ".gitignore", ".dockerignore", "LICENSE"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"{relative}: non UTF-8 text")
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                errors.append(f"{relative}: {label}")
    try:
        cases = json.loads((ROOT / "eval/questions.json").read_text(encoding="utf-8"))
        if not cases or not all(set(case) == {"question", "expected_source"} for case in cases):
            errors.append("eval/questions.json: invalid reference cases")
    except (ValueError, OSError):
        errors.append("eval/questions.json: cannot read evaluation dataset")
    if not (ROOT / "docs/screenshots/workspace.png").is_file():
        errors.append("docs/screenshots/workspace.png: screenshot missing")
    return errors


if __name__ == "__main__":
    violations = audit()
    for item in violations:
        print(f"FAIL: {item}")
    if violations:
        raise SystemExit(1)
    print("PASS: repository content and expected resources")
