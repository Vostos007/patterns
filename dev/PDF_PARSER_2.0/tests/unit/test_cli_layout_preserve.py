from pathlib import Path

import pytest

from kps import cli

pytest.importorskip("langdetect")
pytest.importorskip("fitz")


class DummyRunContext:
    def __init__(self, staged_input: Path, output_dir: Path) -> None:
        self.staged_input = staged_input
        self.output_dir = output_dir


def test_layout_preserve_skips_for_unsupported_langs(capsys, tmp_path):
    ctx = DummyRunContext(tmp_path / "in.pdf", tmp_path / "out")
    ctx.staged_input.write_text("dummy")

    cli._maybe_run_layout_preserver(ctx, ["de"])  # noqa: SLF001
    captured = capsys.readouterr()
    assert "skipped" in captured.out.lower()


def test_layout_preserve_invokes_process(monkeypatch, tmp_path):
    ctx = DummyRunContext(tmp_path / "input.pdf", tmp_path / "output")
    ctx.staged_input.write_text("dummy")

    called = {}

    def fake_process(input_path, out_dir, target_langs, preserve_formatting=False):  # noqa: ANN001
        out_dir.mkdir(parents=True, exist_ok=True)
        produced = out_dir / "foo_en.pdf"
        produced.write_text("dummy")
        called["args"] = (input_path, out_dir, tuple(target_langs))
        return [produced]

    monkeypatch.setattr("kps.layout_preserver.process_pdf", fake_process)

    cli._maybe_run_layout_preserver(ctx, ["en", "ru"])  # noqa: SLF001

    assert "args" in called
    assert called["args"][2] == ("en", "ru")
