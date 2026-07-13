from django.contrib import admin
from .models import Page, PageLink

class PageLinkInline(admin.TabularInline):
    model = PageLink; fk_name = "source"; extra = 0; readonly_fields = ["created_at"]

@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ["title","author","organization_id","updated_at"]
    list_filter = ["author","organization_id","updated_at"]
    search_fields = ["title","body"]
    prepopulated_fields = {"slug":("title",)}
    inlines = [PageLinkInline]
    readonly_fields = ["created_at","updated_at"]

@admin.register(PageLink)
class PageLinkAdmin(admin.ModelAdmin):
    list_display = ["source","target","created_at"]
    search_fields = ["source__title","target__title"]
