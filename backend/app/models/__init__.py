from app.models.base import Base
from app.models.attachment import Attachment
from app.models.customer import Customer
from app.models.customer_product import CustomerProduct
from app.models.department import Department
from app.models.operation_log import OperationLog
from app.models.order import Order, OrderItem
from app.models.permission import Permission
from app.models.process import Process
from app.models.process_skill import ProcessSkillLink
from app.models.process_price import ProcessPrice
from app.models.process_route import ProcessRoute, ProcessRouteStep
from app.models.product import Product
from app.models.report import Report, ReportAudit
from app.models.report_unit import ReportUnit, ReportUnitAudit
from app.models.role import Role, role_permissions
from app.models.salary import SalaryItem
from app.models.sku import Sku
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.trace import TraceCode
from app.models.production_plan import ProductionPlan
from app.models.equipment import Equipment, EquipmentCheck, EquipmentMaintenanceLog, EquipmentMaintenancePlan
from app.models.dictionary import DictType, DictItem
from app.models.salary_allowance import SalaryAllowance
from app.models.salary_slip import SalarySlip
from app.models.material import Supplier, Material, MaterialBom, MaterialBomItem
from app.models.quality import InspectionTemplate, InspectionTemplateItem, DefectCode, InspectionRecord
from app.models.tenant_setting import TenantSetting
from app.models.user import User, user_roles
from app.models.work_order import WorkOrder
from app.models.work_order_piece import WorkOrderPiece
from app.models.export_job import ExportJob
from app.models.print_template import PrintTemplate
from app.models.notification import Notification
from app.models.approval import ApprovalFlow, ApprovalStep
from app.models.attendance import AttendanceRecord
from app.models.employee_skill import Skill, UserSkillLink
from app.models.production_calendar import ProductionCalendarDay
from app.models.code_sequence import CodeSequence
from app.models.shift import Shift, ShiftSchedule
from app.models.supplier import Supplier

from app.models.tenant import Tenant
from app.models.crm import CustomerContact, CrmOpportunity, CrmOpportunityActivity, CustomerTag, CustomerTagLink, CrmLead, CrmLeadActivity, CrmQuotation, CrmQuotationItem, CrmContract, CrmPaymentPlan, CrmWinLossReason, CrmCampaign, CrmCampaignMember, CrmSalesTarget, CrmDataImportJob, CrmDataImportError

from app.models.mrp import MrpPlan, MrpItem
from app.models.subcontract import SubcontractOrder, SubcontractOrderItem, SubcontractSendLog, SubcontractReceiveLog
from app.models.system_version import SystemVersion

__all__ = [
    "Base",
    "Tenant",
    "User",
    "Department",
    "Role",
    "Permission",
    "Attachment",
    "Customer",
    "CustomerProduct",
    "TenantSetting",
    "OperationLog",
    "Product",
    "Sku",
    "Process",
    "ProcessSkillLink",
    "ProcessRoute",
    "ProcessRouteStep",
    "ProcessPrice",
    "Order",
    "OrderItem",
    "WorkOrder",
    "WorkOrderPiece",
    "Task",
    "Report",
    "ReportAudit",
    "ReportUnit",
    "ReportUnitAudit",
    "SalaryItem",
    "TraceCode",
    "ProductionPlan",
    "Equipment",
    "EquipmentCheck",
    "EquipmentMaintenancePlan",
    "EquipmentMaintenanceLog",
    "DictType",
    "DictItem",
    "SalaryAllowance",
    "SalarySlip",
    "Supplier",
    "Material",
    "MaterialBom",
    "MaterialBomItem",
    "ExportJob",
    "PrintTemplate",
    "Notification",
    "AttendanceRecord",
    "ProductionCalendarDay",
    "Skill",
    "UserSkillLink",
    "user_roles",
    "role_permissions",
    "CodeSequence",
    "Shift",
    "ShiftSchedule",
    "InspectionTemplate",
    "InspectionTemplateItem",
    "DefectCode",
    "InspectionRecord",
    "CustomerContact",
    "CrmOpportunity",
    "CrmOpportunityActivity",
    "CustomerTag",
    "CustomerTagLink",
    "CrmLead",
    "CrmLeadActivity",
    "CrmQuotation",
    "CrmQuotationItem",
    "CrmContract",
    "CrmPaymentPlan",
    "CrmWinLossReason",
    "CrmCampaign",
    "CrmCampaignMember",
    "CrmSalesTarget",
    "CrmDataImportJob",
    "CrmDataImportError",
    "TaskAssignment",
    "SystemVersion",
]

from app.models.supplier_statement import SupplierStatement, SupplierStatementItem

from app.models.material_issue import MaterialIssue, MaterialIssueItem, MaterialReturn, MaterialReturnItem
from app.models.warehouse_entry import WarehouseEntry, WarehouseEntryItem
