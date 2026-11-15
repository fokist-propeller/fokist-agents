import json
import subprocess
import urllib.error

from wf.config import BoardLink, RepoLink
from wf.integrations import GitHubClient, JiraClient


def fake_gh(stdout="", returncode=0, stderr=""):
    calls = []

    def runner(args, **kw):
        calls.append(args)
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr=stderr)

    return runner, calls


def test_github_repo_ok():
    runner, calls = fake_gh(stdout=json.dumps({"nameWithOwner": "acme/api"}))
    res = GitHubClient(runner).check_repo(RepoLink("acme/api"))
    assert res.ok and res.detail == "acme/api"
    assert calls[0][:3] == ["gh", "repo", "view"]


def test_github_repo_failure_surfaces_gh_error():
    runner, _ = fake_gh(returncode=1, stderr="GraphQL: Could not resolve to a Repository")
    res = GitHubClient(runner).check_repo(RepoLink("acme/missing"))
    assert not res.ok and "Could not resolve" in res.detail


def test_github_project_uses_owner_and_number():
    runner, calls = fake_gh(stdout=json.dumps({"title": "Backlog"}))
    res = GitHubClient(runner).check_board(BoardLink("github", "acme/3"))
    assert res.ok and res.detail == "Backlog"
    assert calls[0] == ["gh", "project", "view", "3", "--owner", "acme", "--format", "json"]


class FakeResp:
    def __init__(self, body):
        self._body = json.dumps(body).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_jira_board_ok_and_sends_basic_auth():
    seen = {}

    def opener(req, timeout):
        seen["url"] = req.full_url
        seen["auth"] = req.get_header("Authorization")
        return FakeResp({"name": "Platform board"})

    env = {"JIRA_BASE_URL": "https://example.atlassian.net/", "JIRA_EMAIL": "a@b.c", "JIRA_API_TOKEN": "t"}
    res = JiraClient(env, opener).check_board(BoardLink("jira", "12"))
    assert res.ok and res.detail == "Platform board"
    assert seen["url"] == "https://example.atlassian.net/rest/agile/1.0/board/12"
    assert seen["auth"].startswith("Basic ")


def test_jira_missing_credentials_is_reported_not_raised():
    res = JiraClient({}, opener=None).check_board(BoardLink("jira", "12"))
    assert not res.ok and "JIRA_API_TOKEN" in res.detail


def test_jira_http_error_is_reported():
    def opener(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", None, None)

    env = {"JIRA_BASE_URL": "https://x", "JIRA_EMAIL": "a", "JIRA_API_TOKEN": "t"}
    res = JiraClient(env, opener).check_board(BoardLink("jira", "999"))
    assert not res.ok and "HTTP 404" in res.detail
