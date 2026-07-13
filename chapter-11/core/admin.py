from django.contrib import admin
from .models import Page, PageLink, Event

class PageLinkInline(admin.TabularInline): model = PageLink; fk_name = "source"; extra = 0; readonly_fields = ["created_at"]

@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ["title","organization_id","author","updated_at","incoming_count","outgoing_count"]; list_filter = ["organization_id","author","updated_at"]; search_fields = ["title","body"]; prepopulated_fields = {"slug":("title",)}; inlines = [PageLinkInline]; readonly_fields = ["created_at","updated_at","incoming_count","outgoing_count"]

@admin.register(PageLink)
class PageLinkAdmin(admin.ModelAdmin): list_display = ["source","target","organization_id","created_at"]; list_filter = ["organization_id","created_at"]; search_fields = ["source__title","target__title"]

@admin.register(Event)
class EventAdmin(admin.ModelAdmin): list_display = ["event_type","page","actor","timestamp"]; list_filter = ["event_type","timestamp"]; search_fields = ["page__title"]
