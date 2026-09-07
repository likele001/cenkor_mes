# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""供应商 ORM：与物料同文件定义，此处单独导出便于 `from app.models.supplier import Supplier` 写法。"""

from app.models.material import Supplier

__all__ = ["Supplier"]
