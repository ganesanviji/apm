import sys
from unittest.mock import MagicMock
sys.modules['click'] = MagicMock()
sys.modules['rich'] = MagicMock()
sys.modules['rich.console'] = MagicMock()
sys.modules['rich.live'] = MagicMock()
sys.modules['rich.progress'] = MagicMock()

from apm_cli.utils.github_host import build_https_clone_url

def test_gitea_url_construction():
    host = "gitea.example.com"
    repo = "owner/repo"
    token = "my-secret-token"
    
    # Test with token (authenticated)
    url = build_https_clone_url(host, repo, token=token)
    print(f"Authenticated URL: {url}")
    assert url == "https://oauth2:my-secret-token@gitea.example.com/owner/repo.git"
    
    # Test without token (anonymous)
    url_anon = build_https_clone_url(host, repo, token=None)
    print(f"Anonymous URL: {url_anon}")
    assert url_anon == "https://gitea.example.com/owner/repo.git"

if __name__ == "__main__":
    test_gitea_url_construction()
    print("Test passed!")
