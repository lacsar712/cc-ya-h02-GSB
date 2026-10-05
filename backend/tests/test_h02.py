from h02_extra_trap import dirt_armed, form_visible, gate

def test_reader_write_blocked():
    assert gate("reader") is False
    assert form_visible() is False
    assert dirt_armed() is False

def test_writer_allowed():
    assert gate("writer") is True
