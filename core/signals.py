"""
Signals for core app models.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import OutlierPunch

logger = logging.getLogger('core')


@receiver(post_save, sender=OutlierPunch)
def notify_new_outlier(sender, instance, created, **kwargs):
    """
    Send email notification when a new outlier punch is created.
    
    Args:
        sender: The model class (OutlierPunch)
        instance: The actual OutlierPunch instance being saved
        created: Boolean; True if a new record was created
        **kwargs: Additional keyword arguments
    """
    # Only send email for new outliers, not updates
    if not created:
        return
    
    # Check if email notifications are enabled
    email_enabled = getattr(settings, 'OUTLIER_EMAIL_NOTIFICATIONS', False)
    if not email_enabled:
        logger.debug(f"Email notifications disabled. Skipping notification for outlier {instance.id}")
        return
    
    # Get email recipients from settings
    recipients = getattr(settings, 'OUTLIER_EMAIL_RECIPIENTS', [])
    if not recipients:
        logger.warning("No email recipients configured for outlier notifications")
        return
    
    # Get user name for better email context
    user_display = instance.user_name if hasattr(instance, 'user_name') else instance.user_id
    
    # Format the email
    subject = f"⚠️ New Outlier Punch Detected - {user_display}"
    
    message = f"""
A new outlier punch has been detected in the attendance system.

Details:
--------
User: {user_display} (ID: {instance.user_id})
Device: {instance.device.name}
Punch Time: {instance.punch_datetime.strftime('%Y-%m-%d %H:%M:%S')}
Shift Date: {instance.associated_shift_date or 'N/A'}
Reason: {instance.reason}

This punch falls outside the acceptable shift window and requires review.

---
ZKTeco F18 Attendance Bridge System
"""
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
        logger.info(f"Sent outlier notification email for user {instance.user_id} to {len(recipients)} recipient(s)")
    except Exception as e:
        logger.error(f"Failed to send outlier notification email: {str(e)}")
