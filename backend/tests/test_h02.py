from h02_extra_trap import dirt_armed, form_visible, gate

def test_reader_write():
    assert gate("reader") is True
    assert form_visible() is True
    assert dirt_armed() is True
