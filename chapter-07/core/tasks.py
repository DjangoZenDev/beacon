
"""Beacon v0.7 — Background Tasks. Unchanged from Chapter 6."""
from celery import shared_task
from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model
logger = get_task_logger(__name__)


@shared_task(max_retries=3, default_retry_delay=10, bind=True)
def notify_bookmarkers(self, page_id, edited_by_user_id):
    from core.models import Page
    User = get_user_model()
    try:
        page = Page.objects.get(pk=page_id)
    except Page.DoesNotExist:
        logger.warning("notify_bookmarkers: page %s not found", page_id)
        return f"Page {page_id} not found"
    bookmarked_users = User.objects.filter(bookmarks__page=page).exclude(pk=edited_by_user_id)
    notification_count = 0
    for user in bookmarked_users:
        try:
            send_notification(user, page)
            notification_count += 1
        except Exception as exc:
            logger.error("Failed to notify user %s: %s", user.id, exc)
    logger.info("Notified %d users about edit to page %s", notification_count, page_id)
    return f"Notified {notification_count} users"


def send_notification(user, page):
    pass
