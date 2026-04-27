# Create a standalone script to test `is_supported_git_host`
import re

def is_valid_fqdn(hostname: str) -> bool:
    if not hostname:
        return False
    hostname = hostname.split('/')[0]
    pattern = r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)+$"
    return bool(re.match(pattern, hostname))

def is_supported_git_host(hostname: str) -> bool:
    if not hostname:
        return False
    
    # Check GitHub / Azure hosts
    if hostname == "github.com" or hostname.endswith(".ghe.com"):
        return True
    if hostname == "dev.azure.com" or hostname.endswith(".visualstudio.com"):
        return True
    
    # Generic FQDN check
    if is_valid_fqdn(hostname):
        return True
    
    return False

test_hosts = ["github.com", "dev.azure.com", "gitlab.com", "bitbucket.org", "gitea.example.com"]

for host in test_hosts:
    print(f"Host '{host}' is supported: {is_supported_git_host(host)}")
