"""Tests for private Gitea (and generic self-hosted Git) repository installation.

Verifies that:
1. ``GENERIC_APM_TOKEN`` is picked up by the token resolution chain for
   non-GitHub / non-ADO hosts.
2. The resolved token is embedded in the HTTPS clone URL.
3. ``_resolve_dep_token`` no longer returns ``None`` for generic hosts when
   ``GENERIC_APM_TOKEN`` is set.
4. ``_resolve_dep_auth_ctx`` returns a valid ``AuthContext`` for generic hosts.
5. When no token is available, the error hint mentions ``GENERIC_APM_TOKEN``.
6. SSH clone URLs are unaffected (token not embedded in SSH URLs).
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apm_cli.core.auth import AuthResolver
from apm_cli.core.token_manager import GitHubTokenManager
from apm_cli.deps.github_downloader import GitHubPackageDownloader
from apm_cli.models.apm_package import DependencyReference


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_downloader_with_env(env: dict) -> GitHubPackageDownloader:
    """Build a downloader inside a patched env, suppressing credential helpers."""
    with patch.dict(os.environ, env, clear=True), patch(
        "apm_cli.core.token_manager.GitHubTokenManager.resolve_credential_from_git",
        return_value=None,
    ):
        dl = GitHubPackageDownloader()
    # Clear the AuthResolver cache so every test starts clean.
    dl.auth_resolver._cache.clear()
    return dl


# ---------------------------------------------------------------------------
# Token resolution
# ---------------------------------------------------------------------------

class TestGenericTokenResolution:
    """GENERIC_APM_TOKEN must reach AuthResolver._resolve_token for generic hosts."""

    def test_generic_apm_token_resolves_for_gitea(self):
        resolver = AuthResolver()
        with patch.dict(
            os.environ,
            {"GENERIC_APM_TOKEN": "gitea-secret-token"},
            clear=True,
        ), patch(
            "apm_cli.core.token_manager.GitHubTokenManager.resolve_credential_from_git",
            return_value=None,
        ):
            ctx = resolver.resolve("gitea.mycompany.com")
        assert ctx.token == "gitea-secret-token"
        assert ctx.source == "GENERIC_APM_TOKEN"
        assert ctx.host_info.kind == "generic"

    def test_generic_apm_token_resolves_for_gitlab(self):
        resolver = AuthResolver()
        with patch.dict(
            os.environ,
            {"GENERIC_APM_TOKEN": "gl-token-abc"},
            clear=True,
        ), patch(
            "apm_cli.core.token_manager.GitHubTokenManager.resolve_credential_from_git",
            return_value=None,
        ):
            ctx = resolver.resolve("gitlab.example.com")
        assert ctx.token == "gl-token-abc"
        assert ctx.source == "GENERIC_APM_TOKEN"

    def test_generic_apm_token_not_used_for_github(self):
        """GENERIC_APM_TOKEN must NOT bleed into GitHub host resolution."""
        resolver = AuthResolver()
        with patch.dict(
            os.environ,
            {"GENERIC_APM_TOKEN": "gitea-token"},
            clear=True,
        ), patch(
            "apm_cli.core.token_manager.GitHubTokenManager.resolve_credential_from_git",
            return_value=None,
        ):
            ctx = resolver.resolve("github.com")
        # No github-specific token set, so token should be None
        assert ctx.token is None

    def test_no_generic_token_falls_through_to_none(self):
        resolver = AuthResolver()
        with patch.dict(os.environ, {}, clear=True), patch(
            "apm_cli.core.token_manager.GitHubTokenManager.resolve_credential_from_git",
            return_value=None,
        ):
            ctx = resolver.resolve("gitea.mycompany.com")
        assert ctx.token is None
        assert ctx.source == "none"

    def test_git_credential_fill_used_when_no_env_token(self):
        """Credential helpers remain the fallback for generic hosts."""
        resolver = AuthResolver()
        with patch.dict(os.environ, {}, clear=True), patch(
            "apm_cli.core.token_manager.GitHubTokenManager.resolve_credential_from_git",
            return_value="credential-helper-token",
        ):
            ctx = resolver.resolve("gitea.mycompany.com")
        assert ctx.token == "credential-helper-token"
        assert ctx.source == "git-credential-fill"


# ---------------------------------------------------------------------------
# _resolve_dep_token
# ---------------------------------------------------------------------------

class TestResolveDepTokenGeneric:
    """_resolve_dep_token must return the token for generic hosts when set."""

    def test_returns_token_for_gitea_https(self):
        dep = DependencyReference.parse("https://gitea.mycompany.com/org/repo.git")
        dl = _make_downloader_with_env({"GENERIC_APM_TOKEN": "gitea-pat-xyz"})
        dl.auth_resolver._cache.clear()
        with patch.dict(os.environ, {"GENERIC_APM_TOKEN": "gitea-pat-xyz"}, clear=True), patch(
            "apm_cli.core.token_manager.GitHubTokenManager.resolve_credential_from_git",
            return_value=None,
        ):
            token = dl._resolve_dep_token(dep)
        assert token == "gitea-pat-xyz"

    def test_returns_none_when_no_generic_token(self):
        dep = DependencyReference.parse("https://gitea.mycompany.com/org/repo.git")
        dl = _make_downloader_with_env({})
        dl.auth_resolver._cache.clear()
        with patch.dict(os.environ, {}, clear=True), patch(
            "apm_cli.core.token_manager.GitHubTokenManager.resolve_credential_from_git",
            return_value=None,
        ):
            token = dl._resolve_dep_token(dep)
        assert token is None

    def test_returns_token_for_gitlab_fqdn(self):
        dep = DependencyReference.parse("gitlab.example.com/group/repo")
        dl = _make_downloader_with_env({"GENERIC_APM_TOKEN": "gl-secret"})
        dl.auth_resolver._cache.clear()
        with patch.dict(os.environ, {"GENERIC_APM_TOKEN": "gl-secret"}, clear=True), patch(
            "apm_cli.core.token_manager.GitHubTokenManager.resolve_credential_from_git",
            return_value=None,
        ):
            token = dl._resolve_dep_token(dep)
        assert token == "gl-secret"


# ---------------------------------------------------------------------------
# _resolve_dep_auth_ctx
# ---------------------------------------------------------------------------

class TestResolveDepAuthCtxGeneric:
    """_resolve_dep_auth_ctx must return an AuthContext for generic hosts."""

    def test_returns_auth_context_for_gitea(self):
        dep = DependencyReference.parse("https://gitea.mycompany.com/org/repo.git")
        dl = _make_downloader_with_env({"GENERIC_APM_TOKEN": "tok"})
        dl.auth_resolver._cache.clear()
        with patch.dict(os.environ, {"GENERIC_APM_TOKEN": "tok"}, clear=True), patch(
            "apm_cli.core.token_manager.GitHubTokenManager.resolve_credential_from_git",
            return_value=None,
        ):
            ctx = dl._resolve_dep_auth_ctx(dep)
        assert ctx is not None
        assert ctx.token == "tok"
        assert ctx.host_info.kind == "generic"

    def test_returns_auth_context_with_none_token_when_unset(self):
        dep = DependencyReference.parse("https://gitea.mycompany.com/org/repo.git")
        dl = _make_downloader_with_env({})
        dl.auth_resolver._cache.clear()
        with patch.dict(os.environ, {}, clear=True), patch(
            "apm_cli.core.token_manager.GitHubTokenManager.resolve_credential_from_git",
            return_value=None,
        ):
            ctx = dl._resolve_dep_auth_ctx(dep)
        assert ctx is not None
        assert ctx.token is None


# ---------------------------------------------------------------------------
# _build_repo_url — HTTPS token embedding
# ---------------------------------------------------------------------------

class TestBuildRepoUrlGenericToken:
    """Token must be embedded in HTTPS URL for generic hosts when resolved."""

    def test_token_embedded_for_gitea_https(self):
        dl = _make_downloader_with_env({})
        dep = DependencyReference.parse("https://gitea.mycompany.com/org/repo.git")
        url = dl._build_repo_url(
            "org/repo",
            use_ssh=False,
            dep_ref=dep,
            token="gitea-secret",
        )
        assert "gitea-secret@gitea.mycompany.com" in url
        assert url.startswith("https://")

    def test_no_token_plain_https_for_generic(self):
        dl = _make_downloader_with_env({})
        dep = DependencyReference.parse("https://gitea.mycompany.com/org/repo.git")
        url = dl._build_repo_url(
            "org/repo",
            use_ssh=False,
            dep_ref=dep,
            token=None,
        )
        assert "@" not in url.replace("https://", "")
        assert url == "https://gitea.mycompany.com/org/repo"

    def test_empty_token_string_suppresses_embedding(self):
        """Passing token='' explicitly suppresses credentials (TransportSelector plain-HTTPS)."""
        dl = _make_downloader_with_env({})
        dep = DependencyReference.parse("https://gitea.mycompany.com/org/repo.git")
        url = dl._build_repo_url(
            "org/repo",
            use_ssh=False,
            dep_ref=dep,
            token="",
        )
        assert "@" not in url.replace("https://", "")

    def test_ssh_url_not_affected_by_token(self):
        dl = _make_downloader_with_env({})
        dep = DependencyReference.parse("git@gitea.mycompany.com:org/repo.git")
        url = dl._build_repo_url(
            "org/repo",
            use_ssh=True,
            dep_ref=dep,
            token="gitea-secret",
        )
        assert "gitea-secret" not in url
        assert url.startswith("git@")

    def test_github_token_still_works(self):
        """Regression: GitHub tokens must still be embedded for github.com."""
        dl = _make_downloader_with_env({"GITHUB_APM_PAT": "ghp_mytoken"})
        dep = DependencyReference.parse("microsoft/vscode")
        url = dl._build_repo_url(
            "microsoft/vscode",
            use_ssh=False,
            dep_ref=dep,
            token="ghp_mytoken",
        )
        assert "ghp_mytoken@github.com" in url


# ---------------------------------------------------------------------------
# Integration: clone uses token when GENERIC_APM_TOKEN is set
# ---------------------------------------------------------------------------

class TestGiteaPrivateCloneIntegration:
    """End-to-end: _clone_with_fallback uses the token for Gitea HTTPS deps."""

    def test_clone_called_with_token_url(self):
        """The HTTPS URL passed to Repo.clone_from must embed the token."""
        dep = DependencyReference.parse("https://gitea.mycompany.com/org/private-pkg.git")

        captured_urls = []

        def _mock_clone(url, *args, **kwargs):
            captured_urls.append(url)
            mock_repo = MagicMock()
            mock_repo.head.commit.hexsha = "abc123"
            return mock_repo

        with patch.dict(os.environ, {"GENERIC_APM_TOKEN": "gitea-pat"}, clear=True), patch(
            "apm_cli.core.token_manager.GitHubTokenManager.resolve_credential_from_git",
            return_value=None,
        ), patch("apm_cli.deps.github_downloader.Repo") as MockRepo:
            MockRepo.clone_from.side_effect = _mock_clone
            dl = GitHubPackageDownloader()
            target = Path(tempfile.mkdtemp())
            try:
                dl._clone_with_fallback(dep.repo_url, target, dep_ref=dep)
            finally:
                shutil.rmtree(target, ignore_errors=True)

        assert captured_urls, "Repo.clone_from was never called"
        assert any("gitea-pat@gitea.mycompany.com" in u for u in captured_urls), (
            f"Token not found in clone URL(s): {captured_urls}"
        )

    def test_clone_without_token_uses_plain_https(self):
        """Without GENERIC_APM_TOKEN, plain HTTPS is used (SSH or credential helper)."""
        dep = DependencyReference.parse("https://gitea.mycompany.com/org/public-pkg.git")

        captured_urls = []

        def _mock_clone(url, *args, **kwargs):
            captured_urls.append(url)
            mock_repo = MagicMock()
            mock_repo.head.commit.hexsha = "def456"
            return mock_repo

        with patch.dict(os.environ, {}, clear=True), patch(
            "apm_cli.core.token_manager.GitHubTokenManager.resolve_credential_from_git",
            return_value=None,
        ), patch("apm_cli.deps.github_downloader.Repo") as MockRepo:
            MockRepo.clone_from.side_effect = _mock_clone
            dl = GitHubPackageDownloader()
            target = Path(tempfile.mkdtemp())
            try:
                dl._clone_with_fallback(dep.repo_url, target, dep_ref=dep)
            finally:
                shutil.rmtree(target, ignore_errors=True)

        assert captured_urls
        # No token embedded — plain HTTPS URL
        for url in captured_urls:
            sanitized = url.replace("https://", "")
            assert "@" not in sanitized, (
                f"Unexpected token embedded in plain-HTTPS URL: {url}"
            )


# ---------------------------------------------------------------------------
# TokenManager: GENERIC_APM_TOKEN in precedence table
# ---------------------------------------------------------------------------

class TestTokenManagerGenericModules:

    def test_generic_modules_purpose_exists(self):
        mgr = GitHubTokenManager()
        assert "generic_modules" in mgr.TOKEN_PRECEDENCE

    def test_generic_apm_token_is_in_generic_modules(self):
        mgr = GitHubTokenManager()
        assert "GENERIC_APM_TOKEN" in mgr.TOKEN_PRECEDENCE["generic_modules"]

    def test_get_token_for_generic_modules(self):
        mgr = GitHubTokenManager()
        with patch.dict(os.environ, {"GENERIC_APM_TOKEN": "my-gitea-token"}):
            token = mgr.get_token_for_purpose("generic_modules", os.environ)
        assert token == "my-gitea-token"

    def test_get_token_for_generic_modules_absent(self):
        mgr = GitHubTokenManager()
        with patch.dict(os.environ, {}, clear=True):
            token = mgr.get_token_for_purpose("generic_modules", os.environ)
        assert token is None
