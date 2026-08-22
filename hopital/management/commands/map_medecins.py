from django.core.management.base import BaseCommand
from hopital.models import Medecin, CustomUser

class Command(BaseCommand):
    help = 'Map legacy Medecin entries to CustomUser accounts (create users for medecins without users)'

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for m in Medecin.objects.all():
            if not m.email:
                self.stdout.write(self.style.WARNING(f"Medecin {m} has no email, skipping."))
                continue
            user = CustomUser.objects.filter(email__iexact=m.email).first()
            if not user:
                username = m.email
                base = username
                i = 1
                while CustomUser.objects.filter(username=username).exists():
                    username = f"{base}_{i}"
                    i += 1
                user = CustomUser.objects.create_user(username=username, email=m.email)
                user.set_unusable_password()
                user.role = 'medecin'
                user.prenom = m.prenom or ''
                user.nom = m.nom or ''
                user.save()
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Created CustomUser {user.username} for Medecin {m}"))
            else:
                if user.role != 'medecin':
                    user.role = 'medecin'
                    user.save()
                    updated += 1
                    self.stdout.write(self.style.SUCCESS(f"Updated CustomUser {user.username} role->medecin"))
                else:
                    self.stdout.write(self.style.NOTICE(f"CustomUser {user.username} already role medecin"))

        self.stdout.write(self.style.SUCCESS(f"Done. created={created}, updated={updated}"))
