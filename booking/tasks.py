from celery import shared_task
from django.utils import timezone

from .models import Notification
from .notifications import deliver_notification


@shared_task
def deliver_due_notifications():
    ids = list(
        Notification.objects.filter(status=Notification.Status.PENDING, due_at__lte=timezone.now())
        .order_by("due_at")
        .values_list("pk", flat=True)[:100]
    )
    for notification_id in ids:
        deliver_notification(notification_id)
