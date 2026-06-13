"""
Create a default development superuser.

Idempotent: if any superuser already exists, this command is a no-op.
The fixed credentials (admin / admin123) are FOR LOCAL DEV ONLY.
Change the password before deploying.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create a dev superuser (admin / admin123). Idempotent and dev-only.'

    USERNAME = 'admin'
    EMAIL = 'admin@vaishnavi.local'
    PASSWORD = 'admin123'

    def handle(self, *args, **opts):
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.NOTICE('A superuser already exists — leaving it untouched.')
            )
            return

        User.objects.create_superuser(
            username=self.USERNAME,
            email=self.EMAIL,
            password=self.PASSWORD,
        )
        self.stdout.write(self.style.SUCCESS(
            f'Created dev superuser: {self.USERNAME} / {self.PASSWORD}'
        ))
        self.stdout.write(self.style.WARNING(
            'CHANGE THIS PASSWORD before deploying anywhere outside localhost.'
        ))
