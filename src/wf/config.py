"""Workspace config: which GitHub repos and which boards (Jira or GitHub Projects)
the workflow is linked to.

The file holds identifiers only. Credentials come from the environment and are
never written here.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
BOARD_PROVIDERS = ("jira", "github")


class ConfigError(ValueError):
    pass


def default_path() -> Path:
    return Path(os.environ.get("WF_CONFIG", "workflow.json"))


@dataclass(frozen=True)
class RepoLink:
    full_name: str  # "owner/name"


@dataclass(frozen=True)
class BoardLink:
    provider: str  # "jira" or "github"
    # jira: the Jira agile board id, e.g. "12"
    # github: the GitHub Project as "owner/number", e.g. "acme/3"
    ref: str
    label: str = ""


@dataclass
class Config:
    repos: list[RepoLink] = field(default_factory=list)
    boards: list[BoardLink] = field(default_factory=list)

    # --- repos -------------------------------------------------------------

    def add_repo(self, full_name: str) -> bool:
        """Returns False if the repo was already linked."""
        full_name = full_name.strip()
        if not REPO_RE.match(full_name):
            raise ConfigError(f"repo must be OWNER/NAME, got {full_name!r}")
        if any(r.full_name == full_name for r in self.repos):
            return False
        self.repos.append(RepoLink(full_name))
        return True

    def remove_repo(self, full_name: str) -> bool:
        before = len(self.repos)
        self.repos = [r for r in self.repos if r.full_name != full_name]
        return len(self.repos) != before

    # --- boards ------------------------------------------------------------

    def add_board(self, provider: str, ref: str, label: str = "") -> bool:
        """Returns False if the same board was already linked."""
        if provider not in BOARD_PROVIDERS:
            raise ConfigError(f"board provider must be one of {BOARD_PROVIDERS}, got {provider!r}")
        ref = ref.strip()
        if provider == "jira":
            if not ref.isdigit():
                raise ConfigError(f"jira board ref must be a numeric board id, got {ref!r}")
        else:
            m = re.match(r"^([A-Za-z0-9_.-]+)/(\d+)$", ref)
            if not m:
                raise ConfigError(f"github project ref must be OWNER/NUMBER, got {ref!r}")
        if any(b.provider == provider and b.ref == ref for b in self.boards):
            return False
        self.boards.append(BoardLink(provider, ref, label))
        return True

    def remove_board(self, provider: str, ref: str) -> bool:
        before = len(self.boards)
        self.boards = [b for b in self.boards if not (b.provider == provider and b.ref == ref.strip())]
        return len(self.boards) != before

    # --- persistence -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "repos": [{"full_name": r.full_name} for r in self.repos],
            "boards": [{"provider": b.provider, "ref": b.ref, "label": b.label} for b in self.boards],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        cfg = cls()
        for r in data.get("repos", []):
            cfg.add_repo(r["full_name"])
        for b in data.get("boards", []):
            cfg.add_board(b["provider"], b["ref"], b.get("label", ""))
        return cfg


def load(path: Path) -> Config:
    if not path.exists():
        return Config()
    try:
        return Config.from_dict(json.loads(path.read_text()))
    except (json.JSONDecodeError, KeyError) as e:
        raise ConfigError(f"{path} is not a valid workflow config: {e}") from e


def save(cfg: Config, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(cfg.to_dict(), indent=2) + "\n")
    tmp.replace(path)
