from fastapi import APIRouter

from app.api.admin.master.products import router as products_router
from app.api.admin.master.materials import router as materials_router
from app.api.admin.master.suppliers import router as suppliers_router
from app.api.admin.master.boms import router as boms_router
from app.api.admin.master.process_prices import router as process_prices_router
from app.api.admin.master.process_routes import router as process_routes_router
from app.api.admin.master.processes import router as processes_router
from app.api.admin.master.skus import router as skus_router


router = APIRouter()
router.include_router(products_router, prefix="/products", tags=["admin-master-products"])
router.include_router(skus_router, prefix="/skus", tags=["admin-master-skus"])
router.include_router(materials_router, prefix="/materials", tags=["admin-master-materials"])
router.include_router(suppliers_router, prefix="/suppliers", tags=["admin-master-suppliers"])
router.include_router(boms_router, prefix="/boms", tags=["admin-master-boms"])
router.include_router(processes_router, prefix="/processes", tags=["admin-master-processes"])
router.include_router(process_routes_router, prefix="/process-routes", tags=["admin-master-process-routes"])
router.include_router(process_prices_router, prefix="/process-prices", tags=["admin-master-process-prices"])
