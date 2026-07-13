"Beacon v0.12 — Background Tasks."
from celery import shared_task
from celery.utils.log import get_task_logger
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
