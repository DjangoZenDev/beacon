"""
Beacon v0.1 — Custom Template Tags

The `render_wikilinks` filter converts [[Page Title]] syntax in page
bodies into HTML links. This is a simple regex-based filter that runs
at template render time.

Chapter 2 will move wikilink parsing to save time (write-time computation)
to avoid re-parsing on every read. The template filter remains for
display purposes only after that optimization.
"""

import re

from django import template
from django.urls import reverse
from django.utils.html import escape

register = template.Library()

WIKILINK_PATTERN = re.compile(r"\[\[([^\[\]]+?)\]\]")


@register.filter(name="render_wikilinks", is_safe=True)
def render_wikilinks(value):
    """
    Replace [[Page Title]] with HTML links.

    For pages that exist, generates a link to that page.
    For pages that do not exist, generates a link with a 'missing' class
    (these become "wanted pages" in later chapters).
    """
    from core.models import Page  # Avoid circular import.

    # Collect all referenced titles.
    titles = {match.group(1).strip() for match in WIKILINK_PATTERN.finditer(value)}

    # Batch-fetch existing pages for those titles.
    existing = set(
        Page.objects.filter(title__in=titles).values_list("title", flat=True)
    )

    def replace_link(match):
        title = match.group(1).strip()
        escaped_title = escape(title)

        if title in existing:
            # The page exists: render a working link.
            slug = escape(title.lower().replace(" ", "-"))
            url = reverse("page_detail", kwargs={"slug": slug})
            return f'<a href="{url}" class="wikilink">{escaped_title}</a>'
        else:
            # The page does not exist: render a "wanted" link.
            url = reverse("page_edit", kwargs={"slug": "new"})
            return (
                f'<a href="{url}" class="wikilink" '
                f'style="color:var(--color-danger);border-color:var(--color-danger);">'
                f'{escaped_title}</a>'
            )

    return WIKILINK_PATTERN.sub(replace_link, value)
