"""
Beacon v0.7 — DRF Serializers

Chapter 7: Django REST Framework serializers for Page and PageLink.
Exposes the core domain model as a REST API for external consumers
and internal service-to-service communication.
"""

from rest_framework import serializers

from .models import Page, PageLink


class PageLinkSerializer(serializers.ModelSerializer):
    """A directed link between two pages."""

    source_title = serializers.ReadOnlyField(source="source.title")
    target_title = serializers.ReadOnlyField(source="target.title")

    class Meta:
        model = PageLink
        fields = [
            "id",
            "organization_id",
            "source",
            "source_title",
            "target",
            "target_title",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class PageSerializer(serializers.ModelSerializer):
    """A knowledge document with links and link counts."""

    outgoing_links = PageLinkSerializer(many=True, read_only=True)
    incoming_links = PageLinkSerializer(many=True, read_only=True)
    author_username = serializers.ReadOnlyField(source="author.username")

    class Meta:
        model = Page
        fields = [
            "id",
            "organization_id",
            "title",
            "slug",
            "body",
            "author",
            "author_username",
            "incoming_count",
            "outgoing_count",
            "outgoing_links",
            "incoming_links",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "incoming_count",
            "outgoing_count",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        """Create a page with the current user as author."""
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["author"] = request.user
        return super().create(validated_data)


class PageListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views (excludes body)."""

    author_username = serializers.ReadOnlyField(source="author.username")

    class Meta:
        model = Page
        fields = [
            "id",
            "organization_id",
            "title",
            "slug",
            "author",
            "author_username",
            "incoming_count",
            "outgoing_count",
            "updated_at",
        ]
