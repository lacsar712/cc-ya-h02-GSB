"""角色写权限策略：仅现场技师（writer）可提交，观察员（reader）只读。"""


def allow_write(role: str) -> bool:
    return role == "writer"


def should_show_form(can_write: bool) -> bool:
    return bool(can_write)


def should_refresh_after_fail(can_write: bool) -> bool:
    return bool(can_write)


def deny_message() -> str:
    return "仅现场技师可提交偏航记录"


def zero_dirt_on_reject() -> bool:
    return True
