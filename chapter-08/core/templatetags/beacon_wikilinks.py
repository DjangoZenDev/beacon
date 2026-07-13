"""Beacon v0.8 — Wikilinks template tag."""
import re
from django import template
from django.urls import reverse
from django.utils.html import escape
register = template.Library()
W = re.compile(r"\[\[([^\[\]]+?)\]\]")

@register.filter(name="render_wikilinks", is_safe=True)
def render_wikilinks(value):
    from core.models import Page
    titles = {m.group(1).strip() for m in W.finditer(value)}
    existing = set(Page.objects.filter(title__in=titles).values_list("title", flat=True))
    def repl(m):
        t = m.group(1).strip()
        et = escape(t)
        if t in existing:
            return f'<a href="{reverse("page_detail", kwargs={"slug":escape(t.lower().replace(" ","-"))})}" class="wikilink">{et}</a>'
        else:
            return f'<a href="{reverse("page_edit", kwargs={"slug":"new"})}" class="wikilink" style="color:var(--color-danger);border-color:var(--color-danger);">{et}</a>'
    return W.sub(repl, value)
