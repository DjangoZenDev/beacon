"""
Beacon v0.4 — Custom Template Tags

The `render_wikilinks` filter converts [[Page Title]] syntax in page
bodies into HTML links. Unchanged from Chapter 3.
"""

import re

from django import template
from django.urls import reverse
from django.utils.html import escape

register = template.Library()

WIKILINK_PATTERN = re.compile(r"\[\[([^\[\]]+?)\]\]")


@register.filter(name="render_wikilinks", is_safe=True)
def render_wikilinks(value):
    from core.models import Page

    titles = {match.group(1).strip() for match in WIKILINK_PATTERN.finditer(value)}
    existing = set(
        Page.objects.filter(title__in=titles).values_list("title", flat=True)
    )

    def replace_link(match):
        title = match.group(1).strip()
        escaped_title = escape(title)

        if title in existing:
            slug = escape(title.lower().replace(" ", "-"))
            url = reverse("page_detail", kwargs={"slug": slug})
            return f'<a href="{url}" class="wikilink">{escaped_title}</a>'
        else:
            url = reverse("page_edit", kwargs={"slug": "new"})
            return (
                f'<a href="{url}" class="wikilink" '
                f'style="color:var(--color-danger);border-color:var(--color-danger);">'
                f'{escaped_title}</a>'
            )

    return WIKILINK_PATTERN.sub(replace_link, value)
