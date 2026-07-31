from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.material import Material
from app.models.product import Product
from app.models.sku import Sku


def _material_sku_code(material_code: str) -> str:
    code = material_code.strip()
    if len(code) > 60:
        code = code[:60]
    return f"MAT-{code}"


def get_material_by_id(db: Session, material_id: int) -> Material | None:
    return db.scalar(select(Material).where(Material.id == material_id))


def get_material_by_code(db: Session, code: str) -> Material | None:
    return db.scalar(select(Material).where(Material.code == code))


def list_materials(
    db: Session,
    keyword: str | None = None,
    supplier_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
    include_inactive: bool = False,
) -> list[Material]:
    stmt = select(Material)
    if not include_inactive:
        stmt = stmt.where(Material.is_active.is_(True))
    if supplier_id is not None:
        stmt = stmt.where(Material.supplier_id == supplier_id)
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(or_(Material.code.like(kw), Material.name.like(kw)))
    stmt = stmt.order_by(Material.id.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


def get_or_create_material_product(db: Session) -> Product:
    item = db.scalar(select(Product).where(Product.code == "__MATERIAL__"))
    if item:
        return item
    item = Product(code="__MATERIAL__", name="原材料", category="material", unit=None, description=None, is_active=True)
    db.add(item)
    db.flush()
    return item


def create_material(
    db: Session,
    code: str,
    name: str,
    unit: str | None,
    spec: str | None,
    remark: str | None,
    supplier_id: int | None,
    is_active: bool,
) -> Material:
    mp = get_or_create_material_product(db)
    sku_code = _material_sku_code(code)
    sku_exists = db.scalar(select(Sku).where(Sku.code == sku_code))
    if sku_exists:
        raise ValueError("物料编码与系统库存编码冲突")
    sku = Sku(
        product_id=mp.id,
        code=sku_code,
        name=name,
        color=None,
        material=None,
        spec=spec,
        remark=remark,
        is_active=is_active,
    )
    db.add(sku)
    db.flush()
    item = Material(
        code=code,
        name=name,
        unit=unit,
        spec=spec,
        remark=remark,
        supplier_id=supplier_id,
        sku_id=sku.id,
        is_active=is_active,
    )
    db.add(item)
    db.flush()
    return item


def update_material(
    db: Session,
    item: Material,
    code: str | None = None,
    name: str | None = None,
    unit: str | None = None,
    spec: str | None = None,
    remark: str | None = None,
    supplier_id: int | None = None,
    is_active: bool | None = None,
) -> Material:
    sku = db.get(Sku, item.sku_id)
    if code is not None and code != item.code:
        new_sku_code = _material_sku_code(code)
        sku_exists = db.scalar(select(Sku).where(Sku.code == new_sku_code, Sku.id != item.sku_id))
        if sku_exists:
            raise ValueError("物料编码与系统库存编码冲突")
        item.code = code
        if sku:
            sku.code = new_sku_code
    if name is not None:
        item.name = name
        if sku:
            sku.name = name
    if unit is not None:
        item.unit = unit
    if spec is not None:
        item.spec = spec
        if sku:
            sku.spec = spec
    if remark is not None:
        item.remark = remark
        if sku:
            sku.remark = remark
    if supplier_id is not None:
        item.supplier_id = supplier_id
    if is_active is not None:
        item.is_active = is_active
        if sku:
            sku.is_active = is_active
    db.flush()
    return item
