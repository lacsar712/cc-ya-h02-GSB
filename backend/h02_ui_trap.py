from role_bypass import allow_write, should_refresh_after_fail, should_show_form, zero_dirt_on_reject

def can_write(role: str) -> bool:
    return allow_write(role)

def paint_form(user_can_write: bool) -> bool:
    return should_show_form(user_can_write)

def reload_on_fail(user_can_write: bool) -> bool:
    return should_refresh_after_fail(user_can_write)

def leaves_dirt() -> bool:
    return not zero_dirt_on_reject()
