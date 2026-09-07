# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
class BizError(Exception):
    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg
        super().__init__(msg)

