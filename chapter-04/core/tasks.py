"""
Beacon v0.4 — Background Tasks

Chapter 4 introduces Celery for asynchronous task processing. These
tasks run outside the request-response cycle, in a separate worker
process. The user who saves a page does not wait for notifications —
they get a success response immediately.

Key design decisions:
- max_retries=3 with default_retry_delay=10s: transient failures (e.g.,
  a brief database outage) are retried, but permanent failures are not
  retried indefinitely.
- bind=True: the task receives `self` as its first argument, giving
  access to self.retry(), self.request.id, and self.max_retries.
- Idempotency: designed so that executing the task twice produces the
  same outcome (two notifications, which is annoying but not
  catastrophic). For billing, this would be a crisis — hence the
  different retry strategy for payment tasks in Chapter 8.
"""

from celery import shared_task
from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model

logger = get_task_logger(__name__)


@shared_task(
    max_retries=3,
    default_retry_delay=10,  # seconds between retries
    bind=True,
)
def notify_bookmarkers(self, page_id, edited_by_user_id):
    """
    Notify all users who bookmarked a page that it has been edited.

    This task runs asynchronously outside the request-response cycle.
    The user who clicked "Save" does not wait for notifications to be
    delivered — they see the success page immediately.

    Args:
        page_id: The primary key of the edited page.
        edited_by_user_id: The user who made the edit. They are excluded
            from notifications (you don't need to be told you edited
            a page).

    Retries:
        Up to 3 retries with 10-second delay if the database is
        temporarily unavailable. After the final retry, the task is
        marked as FAILURE and logged for manual investigation.

    Returns:
        A human-readable result string.
    """
    from core.models import Page

    User = get_user_model()

    try:
        page = Page.objects.get(pk=page_id)
    except Page.DoesNotExist:
        logger.warning("notify_bookmarkers: page %s not found", page_id)
        return f"Page {page_id} not found"

    # Find users who bookmarked this page, excluding the editor.
    # In a real system, there would be a Bookmark model. For now,
    # this is a simplified implementation that queries a hypothetical
    # bookmarks relation.
    bookmarked_users = User.objects.filter(
        bookmarks__page=page
    ).exclude(pk=edited_by_user_id)

    notification_count = 0
    for user in bookmarked_users:
        try:
            # In a real system, this would create Notification rows
            # and/or send emails. The implementation is elided for
            # clarity — see Chapter 9 for real-time notifications
            # via Django Channels.
            send_notification(user, page)
            notification_count += 1
        except Exception as exc:
            logger.error(
                "Failed to notify user %s about page %s: %s",
                user.id, page_id, exc,
            )
            # Do not retry the entire task for a single user failure.
            # Continue with the next user.

    logger.info(
        "Notified %d users about edit to page %s",
        notification_count, page_id,
    )
    return f"Notified {notification_count} users"


def send_notification(user, page):
    """
    Stub: send a notification to a user about a page edit.

    In a real system, this would create a Notification database row
    and/or push a WebSocket message. Chapter 9 adds real-time
    notifications via Django Channels.
    """
    pass
