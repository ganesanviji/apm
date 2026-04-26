import os
from pathlib import Path
from apm_cli.deps.github_downloader import GitHubPackageDownloader
from apm_cli.models.apm_package import DependencyReference

# Mocking a Gitea host
# A Gitea host: git.example.com
# Repo: user/repo

ref = DependencyReference(
    owner="my-user",
    repo="my-repo",
    host="git.example.com",
    ref="main"
)

downloader = GitHubPackageDownloader()
try:
    url = downloader._build_repo_url("my-user/my-repo", dep_ref=ref)
    print(f"URL: {url}")
    
    # check if in the list
    from apm_cli.utils.github_host import is_supported_git_host
    print(f"Supported: {is_supported_git_host('git.example.com')}")

except Exception as e:
    print(f"Error: {e}")
