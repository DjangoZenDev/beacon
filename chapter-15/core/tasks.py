"Beacon v0.15 — Background Tasks with CDN invalidation."
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
logger = get_task_logger(__name__)

@shared_task(max_retries=3, default_retry_delay=10, bind=True)
def notify_bookmarkers(self, page_id, edited_by_user_id):
    from core.models import Page
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try: page = Page.objects.get(pk=page_id)
    except Page.DoesNotExist: return f"Page {page_id} not found"
    bookmarked_users = User.objects.filter(bookmarks__page=page).exclude(pk=edited_by_user_id)
    count = 0
    for user in bookmarked_users:
        try: count += 1
        except Exception as exc: logger.error("Failed to notify user %s: %s", user.id, exc)
    return f"Notified {count} users"

@shared_task(max_retries=3, default_retry_delay=30, bind=True)
def invalidate_cdn_cache(self, page_slug):
    """Invalidate CloudFront cache for a page after edit."""
    if not getattr(settings, "CDN_ENABLED", False):
        return "CDN not enabled"
    try:
        import boto3
        cf = boto3.client("cloudfront")
        dist_id = settings.AWS_CLOUDFRONT_DISTRIBUTION_ID
        cf.create_invalidation(
            DistributionId=dist_id,
            InvalidationBatch={
                "Paths": {"Quantity": 1, "Items": [f"/page/{page_slug}/*"]},
                "CallerReference": f"beacon-invalidate-{page_slug}-{self.request.id}",
            },
        )
        return f"Invalidated CDN for /page/{page_slug}/"
    except Exception as exc:
        logger.error("CDN invalidation failed: %s", exc)
        raise self.retry(exc=exc)
