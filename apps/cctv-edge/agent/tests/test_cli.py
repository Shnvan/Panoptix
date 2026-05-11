from __future__ import annotations

from typing import Any

from panoptix_edge_agent import cli


def test_parser_accepts_supervise_flag() -> None:
    args = cli.build_parser().parse_args(["--supervise"])

    assert args.supervise is True


def test_main_dispatches_supervise_mode(monkeypatch: Any) -> None:
    calls: list[dict[str, object]] = []

    def fake_run_supervisor(config: object, executor: object) -> int:
        calls.append({"config": config, "executor": executor})
        return 0

    monkeypatch.setenv("PANOPTIX_API_BASE_URL", "http://api.example.test")
    monkeypatch.setenv("PANOPTIX_GATEWAY_ID", "gateway-1")
    monkeypatch.setattr(cli, "_run_supervisor", fake_run_supervisor)

    assert cli.main(["--supervise"]) == 0
    assert len(calls) == 1
