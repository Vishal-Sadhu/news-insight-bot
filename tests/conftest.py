"""Global test safety: no test may accidentally open a real network socket."""

import socket

import pytest


@pytest.fixture(autouse=True)
def block_outbound_network(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("outbound network access is forbidden in tests")

    monkeypatch.setattr(socket.socket, "connect", refuse)
