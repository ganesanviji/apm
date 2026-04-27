import sys
from pathlib import Path
from unittest.mock import MagicMock

# Simulate the structure
sys.path.append("/home/user/apm/src")
from apm_cli.utils.github_host import is_supported_git_host

test_hosts = ["github.com", "dev.azure.com", "gitlab.com", "bitbucket.org", "gitea.example.com"]

for host in test_hosts:
    is_supported = is_supported_git_host(host)
    print(f"Host '{host}' is supported: {is_supported}")
