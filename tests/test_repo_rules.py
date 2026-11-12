"""Regras do projeto verificadas automaticamente: custo, independência da Reforma."""
import hashlib

import yaml

from engine.theme import ROOT

SKIP = {".git", "renders", "__pycache__", ".pytest_cache", ".venv"}


def repo_files():
    for p in ROOT.rglob("*"):
        if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP):
            yield p


def test_no_reforma_assets():
    lines = (ROOT / "tests" / "data" / "reforma_asset_hashes.txt").read_text(encoding="utf-8").splitlines()
    blocked = {ln.split()[0] for ln in lines if ln and not ln.startswith("#")}
    assert len(blocked) > 50
    hits = [str(p.relative_to(ROOT)) for p in repo_files()
            if p.name != "reforma_asset_hashes.txt" and hashlib.sha256(p.read_bytes()).hexdigest() in blocked]
    assert hits == []


def test_no_reforma_names():
    banned = ("SucoTeologico", "EBGaramond", "pack01", "wittenberg", "parchment")
    hits = [str(p.relative_to(ROOT)) for p in repo_files() if any(b.lower() in p.name.lower() for b in banned)]
    assert hits == []


def workflows():
    for p in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        yield p, yaml.safe_load(p.read_text(encoding="utf-8"))


def test_workflows_are_manual_and_bounded():
    found = list(workflows())
    assert found, "nenhum workflow"
    for path, wf in found:
        triggers = wf.get("on", wf.get(True))  # PyYAML lê `on:` como True
        keys = set(triggers) if isinstance(triggers, dict) else {triggers}
        assert keys == {"workflow_dispatch"}, f"{path.name}: gatilhos {keys}"
        assert wf.get("permissions") == {"contents": "read"}, path.name
        assert "concurrency" in wf, path.name
        for job in wf["jobs"].values():
            assert job.get("timeout-minutes", 999) <= 20, path.name
            for step in job["steps"]:
                if "upload-artifact" in str(step.get("uses", "")):
                    assert int(step["with"]["retention-days"]) <= 3, path.name


def test_no_paid_services_in_code():
    banned = ("openai", "elevenlabs", "runwayml", "api.runway", "remotion", "texttospeech.googleapis",
              "polly", "azure.cognitiveservices")
    hits = []
    for p in repo_files():
        if p.suffix in {".py", ".yml", ".yaml", ".txt"} and p.parent.name != "data" and p.name != "test_repo_rules.py":
            text = p.read_text(encoding="utf-8", errors="ignore").lower()
            hits += [f"{p.relative_to(ROOT)}: {b}" for b in banned if b in text]
    assert hits == []
