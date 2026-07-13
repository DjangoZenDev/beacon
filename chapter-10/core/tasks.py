"""Beacon v0.10 — Background Tasks with Idempotency."""
import uuid
from celery import shared_task
from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model
logger = get_task_logger(__name__)

@shared_task(max_retries=3, default_retry_delay=10, bind=True)
def notify_bookmarkers(self, page_id, edited_by_user_id, idempotency_key=None):
    from core.idempotency import check_and_claim, store_result
    from core.models import Page
    if idempotency_key is None: idempotency_key = f"notify:{page_id}:{edited_by_user_id}:{uuid.uuid4().hex[:12]}"
    is_new, previous = check_and_claim(idempotency_key)
    if not is_new: return previous or "Duplicate — already processed"
    User = get_user_model()
    try: page = Page.objects.get(pk=page_id)
    except Page.DoesNotExist: store_result(idempotency_key, {"status":"not_found"}); return f"Page {page_id} not found"
    bookmarked_users = User.objects.filter(bookmarks__page=page).exclude(pk=edited_by_user_id)
    notification_count = 0
    for user in bookmarked_users:
        try: send_notification(user, page); notification_count += 1
        except Exception as exc: logger.error("Failed to notify user %s: %s", user.id, exc)
    result = {"status":"ok","notified":notification_count}
    store_result(idempotency_key, result)
    return f"Notified {notification_count} users"

def send_notification(user, page): pass
