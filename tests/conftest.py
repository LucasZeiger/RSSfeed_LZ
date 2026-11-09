from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# These two upstream HTTP-mocked modules originally still performed live DNS.
# Resolve only their reserved example domain deterministically; keep all URL/IP
# validation and every assertion active. Security tests keep their own resolvers.
import socket
import pytest


@pytest.fixture
def offline_example_dns(monkeypatch):
    original = socket.getaddrinfo

    def resolve(host, port, *args, **kwargs):
        if host in {"example.com", "redirect.example.com"}:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", port))]
        return original(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
