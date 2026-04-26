"""Unit tests for private Gitea (and generic git host) repository authentication.

Tests that APM can authenticate with private repositories on generic git hosts
(Gitea, GitLab, Bitbucket, self-hosted) via GIT_APM_PAT or git credential helpers.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apm_cli.core.auth import AuthResolver, HostInfo
from apm_cli.core.token_manager import GitHubTokenManager
from apm_cli.models.apm_package import DependencyReference


_CRED_FILL_PATCH = patch(
    "apm_cli.core.token_manager.GitHubTokenManager.resolve_credential_from_git",
    return_value=None,
)


# ---------------------------------------------------------------------------
# TokenManager: generic_modules purpose
# ---------------------------------------------------------------------------


class TestTokenManagerGenericModules:
    """Test the new 'generic_modules' purpose in GitHubTokenManager."""

    def test_generic_modules_purpose_exists(self):
        mgr = GitHubTokenManager()
        assert "generic_modules" in mgr.TOKEN_PRECEDENCE

    def test_git_apm_pat_in_generic_modules(self):
        assert "GIT_APM_PAT" in GitHubTokenManager.TOKEN_PRECEDENCE["generic_modules"]

    def test_get_token_for_generic_modules(self):
        with patch.dict(os.environ, {"GIT_APM_PAT": "my-gitea-pat"}, clear=True):
            mgr = GitHubTokenManager()
            token = mgr.get_token_for_purpose("generic_modules")
            assert token == "my-gitea-pat"

    def test_get_token_none_when_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            mgr = GitHubTokenManager()
            token = mgr.get_token_for_purpose("generic_modules")
            assert token is None


# ---------------------------------------------------------------------------
# AuthResolver: GIT_APM_PAT token resolution for generic hosts
# ---------------------------------------------------------------------------


class TestGenericHostTokenResolution:
    """Test that GIT_APM_PAT resolves for generic (Gitea, GitLab, etc.) hosts."""

    def test_git_apm_pat_resolves_for_gitea(self):
        """GIT_APM_PAT is picked up for a Gitea host."""
        with patch.dict(os.environ, {"GIT_APM_PAT": "gitea-token"}, clear=True):
            with _CRED_FILL_PATCH:
                resolver = AuthResolver()
                ctx = resolver.resolve("gitea.myorg.com")
                assert ctx.token == "gitea-token"
                assert ctx.source == "GIT_APM_PAT"
                assert ctx.host_info.kind == "generic"

    def test_git_apm_pat_resolves_for_gitlab(self):
        """GIT_APM_PAT is picked up for a GitLab host."""
        with patch.dict(os.environ, {"GIT_APM_PAT": "gitlab-token"}, clear=True):
            with _CRED_FILL_PATCH:
                resolver = AuthResolver()
                ctx = resolver.resolve("gitlab.com")
                assert ctx.token == "gitlab-token"
                assert ctx.source == "GIT_APM_PAT"

    def test_git_apm_pat_resolves_for_bitbucket(self):
        """GIT_APM_PAT is picked up for Bitbucket."""
        with patch.dict(os.environ, {"GIT_APM_PAT": "bb-token"}, clear=True):
            with _CRED_FILL_PATCH:
                resolver = AuthResolver()
                ctx = resolver.resolve("bitbucket.org")
                assert ctx.token == "bb-token"
                assert ctx.source == "GIT_APM_PAT"

    def test_git_apm_pat_resolves_for_self_hosted_gitea(self):
        """GIT_APM_PAT is picked up for a self-hosted Gitea instance."""
        with patch.dict(os.environ, {"GIT_APM_PAT": "self-hosted-token"}, clear=True):
            with _CRED_FILL_PATCH:
                resolver = AuthResolver()
                ctx = resolver.resolve("git.internal.corp")
                assert ctx.token == "self-hosted-token"
                assert ctx.source == "GIT_APM_PAT"
                assert ctx.host_info.kind == "generic"

    def test_generic_host_falls_back_to_credential_helper(self):
        """Without GIT_APM_PAT, credential fill is tried for generic hosts."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git",
                return_value="cred-token"
            ):
                resolver = AuthResolver()
                ctx = resolver.resolve("gitea.myorg.com")
                assert ctx.token == "cred-token"
                assert ctx.source == "git-credential-fill"

    def test_generic_host_no_token_when_nothing_set(self):
        """No token for generic host when GIT_APM_PAT is unset and no credential helper."""
        with patch.dict(os.environ, {}, clear=True):
            with _CRED_FILL_PATCH:
                resolver = AuthResolver()
                ctx = resolver.resolve("gitea.myorg.com")
                assert ctx.token is None
                assert ctx.source == "none"

    def test_github_token_not_leaked_to_generic_host(self):
        """GITHUB_APM_PAT must NOT be forwarded to a generic (non-GitHub) host.

        Leaking a GitHub PAT to a third-party server is a security issue.
        """
        with patch.dict(os.environ, {"GITHUB_APM_PAT": "github-token"}, clear=True):
            with _CRED_FILL_PATCH:
                resolver = AuthResolver()
                ctx = resolver.resolve("gitea.myorg.com")
                # The GitHub PAT must NOT appear for the generic host
                assert ctx.token != "github-token"
                assert ctx.source != "GITHUB_APM_PAT"

    def test_git_apm_pat_takes_precedence_over_credential_helper_for_generic(self):
        """GIT_APM_PAT beats the git credential helper for generic hosts."""
        with patch.dict(os.environ, {"GIT_APM_PAT": "env-pat-token"}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git",
                return_value="cred-token"
            ):
                resolver = AuthResolver()
                ctx = resolver.resolve("gitea.myorg.com")
                # Env var should win over credential fill
                assert ctx.token == "env-pat-token"
                assert ctx.source == "GIT_APM_PAT"

    def test_github_com_not_affected_by_git_apm_pat(self):
        """GIT_APM_PAT does not change token resolution for github.com."""
        with patch.dict(os.environ, {
            "GITHUB_APM_PAT": "gh-token",
            "GIT_APM_PAT": "generic-token",
        }, clear=True):
            with _CRED_FILL_PATCH:
                resolver = AuthResolver()
                ctx = resolver.resolve("github.com")
                # github.com should use GITHUB_APM_PAT, not GIT_APM_PAT
                assert ctx.token == "gh-token"
                assert ctx.source == "GITHUB_APM_PAT"

    def test_ado_not_affected_by_git_apm_pat(self):
        """GIT_APM_PAT does not change token resolution for Azure DevOps."""
        with patch.dict(os.environ, {
            "ADO_APM_PAT": "ado-token",
            "GIT_APM_PAT": "generic-token",
        }, clear=True):
            resolver = AuthResolver()
            ctx = resolver.resolve("dev.azure.com")
            assert ctx.token == "ado-token"
            assert ctx.source == "ADO_APM_PAT"

    def test_generic_host_resolve_for_dep(self):
        """resolve_for_dep works for a Gitea DependencyReference."""
        with patch.dict(os.environ, {"GIT_APM_PAT": "gitea-token"}, clear=True):
            with _CRED_FILL_PATCH:
                resolver = AuthResolver()
                dep_ref = DependencyReference.parse(
                    "https://gitea.myorg.com/acme/rules.git"
                )
                ctx = resolver.resolve_for_dep(dep_ref)
                assert ctx.token == "gitea-token"
                assert ctx.host_info.kind == "generic"


# ---------------------------------------------------------------------------
# _resolve_dep_token: generic host token flows through to clone
# ---------------------------------------------------------------------------


class TestResolveDepTokenForGenericHosts:
    """Test that _resolve_dep_token returns the token for generic hosts."""

    def test_generic_host_token_returned_when_git_apm_pat_set(self):
        """_resolve_dep_token returns GIT_APM_PAT token for Gitea dep_ref."""
        with patch.dict(os.environ, {"GIT_APM_PAT": "gitea-token"}, clear=True):
            with _CRED_FILL_PATCH:
                from apm_cli.deps.github_downloader import GitHubPackageDownloader
                dl = GitHubPackageDownloader()
                dep_ref = DependencyReference.parse(
                    "https://gitea.myorg.com/acme/rules.git"
                )
                token = dl._resolve_dep_token(dep_ref)
                assert token == "gitea-token"

    def test_generic_host_token_none_when_no_creds(self):
        """_resolve_dep_token returns None for Gitea dep when no creds available."""
        with patch.dict(os.environ, {}, clear=True):
            with _CRED_FILL_PATCH:
                from apm_cli.deps.github_downloader import GitHubPackageDownloader
                dl = GitHubPackageDownloader()
                dep_ref = DependencyReference.parse(
                    "https://gitea.myorg.com/acme/rules.git"
                )
                token = dl._resolve_dep_token(dep_ref)
                assert token is None

    def test_generic_host_auth_ctx_returned_when_git_apm_pat_set(self):
        """_resolve_dep_auth_ctx returns a non-None AuthContext for Gitea dep_ref
        when GIT_APM_PAT is set."""
        with patch.dict(os.environ, {"GIT_APM_PAT": "gitea-token"}, clear=True):
            with _CRED_FILL_PATCH:
                from apm_cli.deps.github_downloader import GitHubPackageDownloader
                dl = GitHubPackageDownloader()
                dep_ref = DependencyReference.parse(
                    "https://gitea.myorg.com/acme/rules.git"
                )
                ctx = dl._resolve_dep_auth_ctx(dep_ref)
                assert ctx is not None
                assert ctx.token == "gitea-token"
                assert ctx.host_info.kind == "generic"

    def test_generic_host_auth_ctx_returned_even_when_no_token(self):
        """_resolve_dep_auth_ctx returns an AuthContext (with token=None) for generic hosts."""
        with patch.dict(os.environ, {}, clear=True):
            with _CRED_FILL_PATCH:
                from apm_cli.deps.github_downloader import GitHubPackageDownloader
                dl = GitHubPackageDownloader()
                dep_ref = DependencyReference.parse(
                    "https://gitea.myorg.com/acme/rules.git"
                )
                ctx = dl._resolve_dep_auth_ctx(dep_ref)
                assert ctx is not None  # No longer None for generic hosts
                assert ctx.token is None


# ---------------------------------------------------------------------------
# _build_repo_url: token embedded in clone URL for generic hosts
# ---------------------------------------------------------------------------


class TestBuildRepoUrlForGenericHosts:
    """Test that _build_repo_url embeds a token for generic (non-GitHub) hosts."""

    def _make_downloader(self, env=None):
        """Build a GitHubPackageDownloader with a clean env."""
        env = env or {}
        with patch.dict(os.environ, env, clear=True):
            with _CRED_FILL_PATCH:
                from apm_cli.deps.github_downloader import GitHubPackageDownloader
                return GitHubPackageDownloader()

    def test_token_embedded_in_url_for_gitea(self):
        """When a token is provided for a Gitea dep, it is embedded in the HTTPS clone URL."""
        dl = self._make_downloader()
        dep_ref = DependencyReference.parse("https://gitea.myorg.com/acme/rules.git")
        url = dl._build_repo_url(
            "acme/rules", use_ssh=False, dep_ref=dep_ref, token="gitea-token"
        )
        assert "gitea-token@" in url
        assert "gitea.myorg.com" in url

    def test_no_token_in_url_for_gitea_when_none(self):
        """No token in URL when token argument is None for Gitea dep."""
        dl = self._make_downloader()
        dep_ref = DependencyReference.parse("https://gitea.myorg.com/acme/rules.git")
        url = dl._build_repo_url(
            "acme/rules", use_ssh=False, dep_ref=dep_ref, token=None
        )
        # Token should not appear at all
        assert "gitea-token" not in url
        # URL should still point to the correct host
        assert "gitea.myorg.com" in url

    def test_empty_string_token_means_no_token_for_gitea(self):
        """Empty string token (explicit 'no token' sentinel) produces clean URL."""
        dl = self._make_downloader()
        dep_ref = DependencyReference.parse("https://gitea.myorg.com/acme/rules.git")
        url = dl._build_repo_url(
            "acme/rules", use_ssh=False, dep_ref=dep_ref, token=""
        )
        # Empty token is the 'suppress token' sentinel -- no credentials in URL
        assert "@gitea.myorg.com" not in url or url.startswith("https://gitea.myorg.com")

    def test_ssh_url_for_gitea_no_token(self):
        """SSH URL for Gitea never embeds a token."""
        dl = self._make_downloader()
        dep_ref = DependencyReference.parse("ssh://git@gitea.myorg.com/acme/rules.git")
        url = dl._build_repo_url(
            "acme/rules", use_ssh=True, dep_ref=dep_ref, token="gitea-token"
        )
        assert url.startswith("git@") or "ssh" in url
        # No token embedded in SSH URLs
        assert "gitea-token" not in url

    def test_github_token_still_works_for_github(self):
        """GitHub hosts still get the GITHUB_APM_PAT token embedded."""
        dl = self._make_downloader()
        dep_ref = DependencyReference.parse("https://github.com/microsoft/apm.git")
        url = dl._build_repo_url(
            "microsoft/apm", use_ssh=False, dep_ref=dep_ref, token="gh-token"
        )
        assert "gh-token@" in url
        assert "github.com" in url


# ---------------------------------------------------------------------------
# Error messages: generic host failure suggests GIT_APM_PAT
# ---------------------------------------------------------------------------


class TestGenericHostErrorMessages:
    """Test that clone/ref-listing failures on generic hosts suggest GIT_APM_PAT."""

    def test_clone_error_mentions_git_apm_pat(self):
        """Clone failure for a private Gitea repo mentions GIT_APM_PAT."""
        import tempfile
        from git.exc import GitCommandError
        from apm_cli.deps.github_downloader import GitHubPackageDownloader

        with patch.dict(os.environ, {}, clear=True):
            with _CRED_FILL_PATCH:
                with patch("apm_cli.deps.github_downloader.Repo") as mock_repo:
                    mock_repo.clone_from.side_effect = GitCommandError(
                        "clone", 128, "Authentication failed"
                    )

                    dl = GitHubPackageDownloader()
                    dep_ref = DependencyReference.parse(
                        "https://gitea.myorg.com/acme/rules.git"
                    )
                    with tempfile.TemporaryDirectory() as tmp:
                        with pytest.raises(RuntimeError) as exc_info:
                            dl._clone_with_fallback(
                                "acme/rules",
                                Path(tmp) / "dest",
                                dep_ref=dep_ref,
                            )

                    error = str(exc_info.value)
                    assert "GIT_APM_PAT" in error

    def test_list_remote_refs_error_mentions_git_apm_pat(self):
        """list_remote_refs failure for private Gitea repo mentions GIT_APM_PAT."""
        from git.exc import GitCommandError
        from apm_cli.deps.github_downloader import GitHubPackageDownloader

        with patch.dict(os.environ, {}, clear=True):
            with _CRED_FILL_PATCH:
                with patch("apm_cli.deps.github_downloader.git") as mock_git:
                    cmd_mock = MagicMock()
                    mock_git.cmd.Git.return_value = cmd_mock
                    cmd_mock.ls_remote.side_effect = GitCommandError(
                        "ls-remote", 128, "Authentication failed"
                    )

                    dl = GitHubPackageDownloader()
                    dep_ref = DependencyReference.parse(
                        "https://gitea.myorg.com/acme/rules.git"
                    )
                    with pytest.raises(RuntimeError) as exc_info:
                        dl.list_remote_refs(dep_ref)

                    error = str(exc_info.value)
                    assert "GIT_APM_PAT" in error
