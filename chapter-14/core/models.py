
"""Beacon v0.14 — Core Models (carried from Ch13)."""

import re
from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Page(models.Model):
    organization_id = models.IntegerField(db_index=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pages")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    incoming_count = models.PositiveIntegerField(default=0)
    outgoing_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = [["organization_id", "slug"]]
        indexes = [
            models.Index(fields=["organization_id", "slug"], name="page_org_slug_idx"),
            models.Index(fields=["organization_id", "-updated_at"], name="page_org_updated_idx"),
            models.Index(fields=["organization_id", "-incoming_count"], name="page_org_incoming_idx"),
            models.Index(fields=["author", "-created_at"], name="page_author_created_idx"),
        ]

    def __str__(self): return f"[org:{self.organization_id}] {self.title}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.slug: self.slug = slugify(self.title)
        super().save(*args, **kwargs)
        cache.delete(f"page:{self.organization_id}:{self.slug}")
        self._invalidate_page_lists()
        self._rebuild_links()
        try:
            from .outbox import enqueue_outbox
            ev = "page.created" if is_new else "page.updated"
            enqueue_outbox("beacon.events.pages", {"type":ev,"payload":{"page_id":self.pk,"organization_id":self.organization_id,"title":self.title,"slug":self.slug}})
        except Exception: pass

    def delete(self, *args, **kwargs):
        slug, org_id, pk = self.slug, self.organization_id, self.pk
        super().delete(*args, **kwargs)
        cache.delete(f"page:{org_id}:{slug}"); self._invalidate_page_lists()
        try:
            from .outbox import enqueue_outbox
            enqueue_outbox("beacon.events.pages", {"type":"page.deleted","payload":{"page_id":pk,"organization_id":org_id}})
        except Exception: pass

    def _invalidate_page_lists(self):
        try:
            keys = cache.keys(f"page_list:{self.organization_id}:*")
            if keys: cache.delete_many(keys)
        except Exception: pass

    def _rebuild_links(self):
        PageLink.objects.filter(source=self).delete()
        for title in re.findall(r"\[\[([^\[\]]+?)\]\]", self.body):
            try: target = Page.objects.get(organization_id=self.organization_id, title__iexact=title.strip())
            except Page.DoesNotExist: continue
            if target.pk != self.pk: PageLink.objects.get_or_create(source=self, target=target)

    def get_absolute_url(self): return reverse("page_detail", kwargs={"slug": self.slug})
    @property
    def link_count(self): return self.outgoing_links.count()


class PageLink(models.Model):
    organization_id = models.IntegerField(db_index=True)
    source = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="outgoing_links")
    target = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="incoming_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["source", "target"]]; ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization_id", "source"], name="pagelink_org_src_idx"),
            models.Index(fields=["organization_id", "target"], name="pagelink_org_tgt_idx"),
        ]

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new and not self.organization_id: self.organization_id = self.source.organization_id
        super().save(*args, **kwargs)
        if is_new:
            Page.objects.filter(pk=self.source_id).update(outgoing_count=models.F("outgoing_count")+1)
            Page.objects.filter(pk=self.target_id).update(incoming_count=models.F("incoming_count")+1)

    def delete(self, *args, **kwargs):
        sid, tid = self.source_id, self.target_id
        super().delete(*args, **kwargs)
        Page.objects.filter(pk=sid).update(outgoing_count=models.F("outgoing_count")-1)
        Page.objects.filter(pk=tid).update(incoming_count=models.F("incoming_count")-1)
