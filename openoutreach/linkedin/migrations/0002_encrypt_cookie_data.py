# Generated migration to encrypt cookie_data into cookie_data_encrypted
from __future__ import annotations

from django.db import migrations, models


def forwards(apps, schema_editor):
    LinkedInProfile = apps.get_model("linkedin", "LinkedInProfile")
    # Avoid importing project crypto directly in migrations; derive key from settings as in runtime
    import base64
    import hashlib
    import json

    from cryptography.fernet import Fernet
    from django.conf import settings

    def _derive_key(secret: str, salt: str = "openoutreach-cookie-salt") -> bytes:
        h = hashlib.sha256()
        h.update(secret.encode("utf-8"))
        h.update(salt.encode("utf-8"))
        return base64.urlsafe_b64encode(h.digest())

    secret = getattr(settings, "SECURE_COOKIE_MIGRATION_SECRET", None) or getattr(
        settings, "SECRET_KEY"
    )
    if not secret:
        # Nothing to do
        return
    key = _derive_key(secret)
    f = Fernet(key)

    for profile in LinkedInProfile.objects.all():
        try:
            cookie_data = getattr(profile, "cookie_data", None)
            if cookie_data is None:
                continue
            text = json.dumps(cookie_data)
            token = f.encrypt(text.encode("utf-8"))
            encoded = base64.urlsafe_b64encode(token).decode("utf-8")
            profile.cookie_data_encrypted = encoded
            # Use update_fields to avoid triggering model property logic
            profile.save(update_fields=["cookie_data_encrypted"])
        except Exception:
            # Skip problematic rows
            continue


def backwards(apps, schema_editor):
    LinkedInProfile = apps.get_model("linkedin", "LinkedInProfile")
    import base64
    import hashlib
    import json

    from cryptography.fernet import Fernet
    from django.conf import settings

    def _derive_key(secret: str, salt: str = "openoutreach-cookie-salt") -> bytes:
        h = hashlib.sha256()
        h.update(secret.encode("utf-8"))
        h.update(salt.encode("utf-8"))
        return base64.urlsafe_b64encode(h.digest())

    secret = getattr(settings, "SECURE_COOKIE_MIGRATION_SECRET", None) or getattr(
        settings, "SECRET_KEY"
    )
    if not secret:
        return
    key = _derive_key(secret)
    f = Fernet(key)

    for profile in LinkedInProfile.objects.all():
        try:
            enc = profile.cookie_data_encrypted
            if not enc:
                continue
            token = base64.urlsafe_b64decode(enc.encode("utf-8"))
            text = f.decrypt(token).decode("utf-8")
            profile.cookie_data = json.loads(text)
            profile.save(update_fields=["cookie_data"])
        except Exception:
            continue


class Migration(migrations.Migration):
    dependencies = [("linkedin", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="linkedinprofile",
            name="cookie_data_encrypted",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(model_name="linkedinprofile", name="cookie_data"),
    ]
