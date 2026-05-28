from __future__ import annotations

import logging
import os

from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Profile
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=User)
def post_save_create_profile(sender, instance, created, *args, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    instance.profile.save()



"""
signals.py — Profile Image Auto-Cleanup
KwikSchools — Smarter Schools!

Place this in your users/signals.py (or wherever your Profile model lives).
Make sure your app's AppConfig.ready() calls:
    from . import signals  # noqa

────────────────────────────────────────────────────────────────────────────
HOW IT WORKS
────────────────────────────────────────────────────────────────────────────
  pre_save  → fires BEFORE the new image is written to DB
              → fetches the OLD profile from DB
              → if the image field changed AND the old file exists on disk
                AND it is not the default image → deletes the old file

  The model's save() method is also patched to do the same check inline
  so it works whether you use signals or call profile.save() directly.
────────────────────────────────────────────────────────────────────────────
"""
# from __future__ import annotations

# import logging
# import os

# from django.db.models.signals import pre_save
# from django.dispatch import receiver

logger = logging.getLogger(__name__)

# The default image filename — never delete this one
DEFAULT_IMAGE_NAME = 'default.jpg'


def _delete_old_image(old_image_field, new_image_field) -> None:
    """
    Delete the file referenced by old_image_field if:
      - it exists on disk
      - it is not the default image
      - it differs from the incoming new image
    """
    if not old_image_field:
        return  # no previous image stored

    old_name = str(old_image_field)
    new_name = str(new_image_field) if new_image_field else ''

    # Don't delete if the image hasn't changed
    if old_name == new_name:
        return

    # Never delete the default image
    if os.path.basename(old_name) == DEFAULT_IMAGE_NAME:
        return

    # Attempt to get the real file path and delete it
    try:
        old_path = old_image_field.path  # raises ValueError if no file associated
        if os.path.isfile(old_path):
            os.remove(old_path)
            logger.info(f'Deleted old profile image: {old_path}')
        else:
            logger.debug(f'Old profile image not found on disk (already removed?): {old_path}')
    except (ValueError, AttributeError):
        # ImageField.path raises ValueError when the name is blank/empty
        pass
    except OSError as e:
        # Non-fatal — log and continue. Upload still succeeds.
        logger.warning(f'Could not delete old profile image "{old_name}": {e}')


# ── Signal handler ────────────────────────────────────────────────────────────

@receiver(pre_save, sender='users.Profile')
def delete_old_profile_image_on_update(sender, instance, **kwargs):
    """
    Fires before Profile.save().
    Compares the incoming image with the current DB record and deletes
    the old file if it has changed.

    NOTE: sender='users.Profile' uses a string reference so this
    signal registration works even before the model is fully loaded.
    Change 'accounts' to your actual app label if different.
    """
    if not instance.pk:
        # New profile being created — nothing to delete
        return

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    _delete_old_image(old_instance.image, instance.image)


# ── Updated Profile.save() patch ─────────────────────────────────────────────
# 
# ALTERNATIVE: If you prefer not to use signals, replace your Profile.save()
# with the version below. It does the same thing inline.
#
# def save(self, *args, **kwargs):
#     # ── Auto-generate referral code ───────────────────────────────────
#     if self.code == "":
#         self.code = generate_ref_code()
#
#     # ── Delete old profile image if it changed ────────────────────────
#     if self.pk:
#         try:
#             old = Profile.objects.get(pk=self.pk)
#             _delete_old_image(old.image, self.image)
#         except Profile.DoesNotExist:
#             pass
#
#     super().save(*args, **kwargs)
