"""Single source of truth for CRM request schemas.

Previously each `*_api.py` module declared its own `XIn`/`XPatchIn`
pair, so the create/patch contract for a given entity lived in two
places and drifted easily. Collecting every pair here keeps each
entity's full input contract reviewable in one screen.

The `PatchIn` variants are intentionally hand-written (all fields
optional, no defaults) rather than derived from `XIn` via
metaprogramming: these schemas are the API validation contract and
there is no per-field integration coverage that would catch a
behaviour change from an automatic transform.
"""
from __future__ import annotations

from ninja import Field, Schema

# --- Contacts ---------------------------------------------------------------

class ContactIn(Schema):
    first_name: str
    last_name: str = ''
    phone: str = ''
    email: str = ''
    messenger_id: str = ''
    position: str = ''
    company_id: int | None = None
    custom_fields: dict = {}
    source: str = ''
    responsible_id: int | None = None


class ContactPatchIn(Schema):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    messenger_id: str | None = None
    position: str | None = None
    company_id: int | None = None
    custom_fields: dict | None = None
    source: str | None = None
    responsible_id: int | None = None


# --- Companies --------------------------------------------------------------

class CompanyIn(Schema):
    name: str
    inn: str = Field('', max_length=12)
    phone: str = Field('', max_length=50)
    email: str = ''
    address: str = ''
    website: str = ''
    custom_fields: dict = {}
    responsible_id: int | None = None


class CompanyPatchIn(Schema):
    name: str | None = None
    inn: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    website: str | None = None
    custom_fields: dict | None = None
    responsible_id: int | None = None


# --- Pipelines & Stages -----------------------------------------------------

class PipelineIn(Schema):
    name: str
    is_default: bool = False
    sort_order: int = 0
    is_active: bool = True


class PipelinePatchIn(Schema):
    name: str | None = None
    is_default: bool | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class StageIn(Schema):
    name: str
    stage_type: str = 'open'
    color: str = '#3B82F6'
    sort_order: int = 0
    auto_action: dict = {}


class StagePatchIn(Schema):
    name: str | None = None
    stage_type: str | None = None
    color: str | None = None
    sort_order: int | None = None
    auto_action: dict | None = None


# --- Deals ------------------------------------------------------------------

class DealIn(Schema):
    name: str
    pipeline_id: int
    stage_id: int
    contact_id: int | None = None
    company_id: int | None = None
    amount: float | None = None
    currency: str = 'RUB'
    responsible_id: int | None = None
    expected_close_date: str | None = None
    loss_reason: str = ''
    custom_fields: dict = {}
    source: str = ''


class DealPatchIn(Schema):
    name: str | None = None
    pipeline_id: int | None = None
    stage_id: int | None = None
    contact_id: int | None = None
    company_id: int | None = None
    amount: float | None = None
    currency: str | None = None
    responsible_id: int | None = None
    expected_close_date: str | None = None
    loss_reason: str | None = None
    custom_fields: dict | None = None
    source: str | None = None


class DealMoveIn(Schema):
    stage_id: int


# --- Activities -------------------------------------------------------------

class ActivityIn(Schema):
    activity_type: str
    deal_id: int | None = None
    contact_id: int | None = None
    responsible_id: int | None = None
    title: str
    body: str = ''
    status: str = 'done'
    due_date: str | None = None


class ActivityPatchIn(Schema):
    activity_type: str | None = None
    deal_id: int | None = None
    contact_id: int | None = None
    responsible_id: int | None = None
    title: str | None = None
    body: str | None = None
    status: str | None = None
    due_date: str | None = None


# --- Catalog (products) -----------------------------------------------------

class ProductIn(Schema):
    name: str
    sku: str = ''
    category_id: int | None = None
    unit: str = 'pcs'
    price: float = 0
    currency: str = 'RUB'
    vat_rate: float = 20
    description: str = ''
    is_active: bool = True
    custom_fields: dict = {}


class ProductPatchIn(Schema):
    name: str | None = None
    sku: str | None = None
    category_id: int | None = None
    unit: str | None = None
    price: float | None = None
    currency: str | None = None
    vat_rate: float | None = None
    description: str | None = None
    is_active: bool | None = None
    custom_fields: dict | None = None


# --- Deal items -------------------------------------------------------------

class DealItemIn(Schema):
    product_id: int
    quantity: float = 1
    price: float | None = None          # None → текущая цена товара (снимок)
    discount_percent: float = 0
    vat_rate: float | None = None       # None → ставка из товара


class DealItemPatchIn(Schema):
    quantity: float | None = None
    price: float | None = None
    discount_percent: float | None = None
    vat_rate: float | None = None
    sort_order: int | None = None


# --- Web forms --------------------------------------------------------------

class WebFormFieldIn(Schema):
    key: str
    label: str
    type: str = 'text'        # text | email | phone | textarea | select
    required: bool = False
    options: list[str] = []


class WebFormIn(Schema):
    name: str
    fields_schema: list[WebFormFieldIn] = []
    pipeline_id: int
    stage_id: int
    source: str = 'webform'
    auto_distribute: bool = True
    success_message: str = 'Спасибо! Мы свяжемся с вами.'
    allowed_origins: list[str] = []
    is_active: bool = True


class WebFormPatchIn(Schema):
    name: str | None = None
    fields_schema: list[WebFormFieldIn] | None = None
    pipeline_id: int | None = None
    stage_id: int | None = None
    source: str | None = None
    auto_distribute: bool | None = None
    success_message: str | None = None
    allowed_origins: list[str] | None = None
    is_active: bool | None = None


# --- Tags & segments --------------------------------------------------------

class TagIn(Schema):
    name: str
    color: str = '#6366F1'


class TagPatchIn(Schema):
    name: str | None = None
    color: str | None = None


class TagAssignIn(Schema):
    tag_ids: list[int] = []


class SegmentIn(Schema):
    name: str
    entity: str = 'contacts'
    filters: dict = {}


class SegmentPatchIn(Schema):
    name: str | None = None
    entity: str | None = None
    filters: dict | None = None


# --- Automation rules -------------------------------------------------------

class AutomationRuleIn(Schema):
    name: str
    trigger: str            # new_deal | stage_changed | no_activity
    conditions: dict = {}
    action: dict = {}       # {type, title, days_offset, event, stage_id, responsible_id}
    is_active: bool = True
    priority: int = 0


class AutomationRulePatchIn(Schema):
    name: str | None = None
    trigger: str | None = None
    conditions: dict | None = None
    action: dict | None = None
    is_active: bool | None = None
    priority: int | None = None


# --- Import / merge ---------------------------------------------------------

class MergeIn(Schema):
    primary_id: int
    merged_ids: list[int] = []
