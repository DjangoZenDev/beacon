"Beacon v0.15 — Serializers."
from rest_framework import serializers
from .models import Page

class PageSerializer(serializers.ModelSerializer):
    incoming_count = serializers.IntegerField(read_only=True)
    outgoing_count = serializers.IntegerField(read_only=True)
    author_name = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = Page
        fields = ["id","title","slug","body","author","author_name","organization_id","incoming_count","outgoing_count","created_at","updated_at"]
        read_only_fields = ["id","slug","author","created_at","updated_at"]
