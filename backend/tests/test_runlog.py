import re
import threading

from runlog import RunLogger, describe_exc

LINE = re.compile(r"^\[\d\d:\d\d:\d\d\] \[\+\d+\.\d+s\] (INFO |WARN |ERROR|STAGE) ")


def test_describe_exc_plain():
    assert describe_exc(RuntimeError("provider kosong")) == "RuntimeError: provider kosong"


def test_lines_format_dan_file(tmp_path):
    rl = RunLogger(7, "manual", log=lambda _l: None, log_dir=str(tmp_path))
    rl.info("mulai")
    with rl.stage("persiapan"):
        rl.warn("lambat")
    try:
        raise ValueError("boom")
    except ValueError as e:
        rl.error("gagal", exc=e)
    rl.finish("failed", ok=0, failed=1)

    body = [l for l in rl.lines if not l.startswith("===")]
    tb_start = body.index([l for l in body if l.startswith("Traceback")][0])
    for line in body[:tb_start]:
        assert LINE.match(line), line
    assert rl.lines[0].startswith("=== run #7 trigger=manual start ")
    assert rl.lines[-1].startswith("=== run #7 failed in ") and "ok=0 failed=1" in rl.lines[-1]
    assert sum("── persiapan" in l for l in rl.lines) == 2
    assert (tmp_path / "run_7.log").read_text() == "\n".join(rl.lines) + "\n"


def test_stage_gagal_tetap_raise(tmp_path):
    rl = RunLogger(1, "manual", log=lambda _l: None, log_dir=str(tmp_path))
    try:
        with rl.stage("browser"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert any("browser gagal setelah" in l for l in rl.lines)


def test_log_dir_tidak_bisa_ditulis(tmp_path):
    f = tmp_path / "bukan-dir"
    f.write_text("x")
    rl = RunLogger(1, "manual", log=lambda _l: None, log_dir=str(f / "sub"))
    rl.info("tetap jalan")
    assert any("tetap jalan" in l for l in rl.lines)


def test_child_prefix_dan_thread_safe(tmp_path):
    rl = RunLogger(2, "manual", log=lambda _l: None, log_dir=str(tmp_path))
    slog = rl.child("slot 3")
    slog.info("hai"); slog.warn("awas"); slog.err("rusak"); slog.ok("beres"); slog.step("lanjut")
    assert any("INFO  [slot 3] hai" in l for l in rl.lines)
    assert any("WARN  [slot 3] awas" in l for l in rl.lines)
    assert any("ERROR [slot 3] rusak" in l for l in rl.lines)

    def spam(i):
        for k in range(200):
            rl.child(f"t{i}").info(f"baris {k}")

    ts = [threading.Thread(target=spam, args=(i,)) for i in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    body = [l for l in rl.lines if LINE.match(l)]
    assert len(body) == 5 + 8 * 200
    assert all(LINE.match(l) for l in body)  # tidak ada baris tercampur
    rl.finish("success", ok=0)
    assert (tmp_path / "run_2.log").read_text().count("\n") == len(rl.lines)
