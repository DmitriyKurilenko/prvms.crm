from django.contrib import admin

from .models import (
    Activity,
    AutomationRule,
    Company,
    Contact,
    Deal,
    DealItem,
    Pipeline,
    Product,
    ProductCategory,
    Segment,
    Stage,
    Tag,
    WebForm,
)


@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'trigger', 'is_active', 'priority', 'created_at')
    list_filter = ('trigger', 'is_active')


@admin.register(WebForm)
class WebFormAdmin(admin.ModelAdmin):
    list_display = ('name', 'pipeline', 'stage', 'is_active', 'submissions_count', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'color', 'created_at')
    search_fields = ('name',)


@admin.register(Segment)
class SegmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'entity', 'created_at')
    list_filter = ('entity',)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'phone', 'email', 'source', 'created_at')
    search_fields = ('first_name', 'last_name', 'phone', 'email')


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'inn', 'phone', 'email', 'created_at')
    search_fields = ('name', 'inn')


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_default', 'sort_order', 'is_active')
    list_filter = ('is_active',)


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ('name', 'pipeline', 'stage_type', 'sort_order', 'color')
    list_filter = ('pipeline', 'stage_type')


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ('name', 'pipeline', 'stage', 'amount', 'responsible', 'created_at')
    list_filter = ('pipeline', 'stage')
    search_fields = ('name',)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('title', 'activity_type', 'deal', 'contact', 'status', 'created_at')
    list_filter = ('activity_type', 'status')


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'sort_order')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'unit', 'price', 'vat_rate', 'is_active', 'created_at')
    list_filter = ('is_active', 'unit')
    search_fields = ('name', 'sku')


@admin.register(DealItem)
class DealItemAdmin(admin.ModelAdmin):
    list_display = ('name_snapshot', 'deal', 'quantity', 'price', 'vat_rate')
    search_fields = ('name_snapshot',)
