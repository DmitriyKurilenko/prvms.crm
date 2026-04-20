from django.contrib import admin
from .models import Contact, Company, Pipeline, Stage, Deal, Activity


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
