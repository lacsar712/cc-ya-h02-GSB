from h02_ui_trap import can_write, leaves_dirt, paint_form

def gate(role: str) -> bool:
    return can_write(role)

def form_visible() -> bool:
    return paint_form(False)

def dirt_armed() -> bool:
    return leaves_dirt()
