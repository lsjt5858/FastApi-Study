"""task-7 引入：自定义 Annotated 类型。

PhoneNumber 用 Annotated + AfterValidator 校验，可在多个模型复用。
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator

# 国际手机号格式：可选 + 开头，10~15 位数字
_PHONE_RE = re.compile(r"\+?\d{10,15}")


def _validate_phone(value: str) -> str:
    if not _PHONE_RE.fullmatch(value):
        raise ValueError(f"Invalid phone number: {value}")
    return value


# 自定义类型：用 Annotated 包装 str + AfterValidator
PhoneNumber = Annotated[str, AfterValidator(_validate_phone)]
