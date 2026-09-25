from grimoire.fsutil import read_lines, slug, write_atomic, write_lines


def test_slug():
    assert slug("fa-686 (data migration)") == "fa-686-data-migration"
    assert slug("  Main:Editor  ") == "main-editor"
    assert slug("!!!") == "workspace"


def test_round_trip_keeps_crlf_and_drops_bom(tmp_path):
    p = tmp_path / "a.md"
    p.write_bytes(b"\xef\xbb\xbfone\r\ntwo\r\n")
    lines, nl = read_lines(p)
    assert lines == ["one", "two"]
    assert nl == "\r\n"
    write_lines(p, lines + ["three"], nl)
    assert p.read_bytes() == b"one\r\ntwo\r\nthree\r\n"


def test_read_lines_lf(tmp_path):
    p = tmp_path / "b.md"
    p.write_bytes(b"x\ny\n")
    assert read_lines(p) == (["x", "y"], "\n")


def test_write_atomic_creates_parents_and_leaves_no_temp(tmp_path):
    p = tmp_path / "deep" / "dir" / "c.txt"
    write_atomic(p, "héllo — ok\n")
    assert p.read_text(encoding="utf-8") == "héllo — ok\n"
    assert [x.name for x in p.parent.iterdir()] == ["c.txt"]
