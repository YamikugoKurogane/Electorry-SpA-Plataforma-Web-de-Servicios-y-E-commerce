from django.core.management.base import BaseCommand

from apps.notificaciones.services import reintentar_pendientes


class Command(BaseCommand):
    help = "Reintenta el envío de notificaciones pendientes (programar con cron cada 5-10 minutos)."

    def handle(self, *args, **options):
        n = reintentar_pendientes()
        self.stdout.write(self.style.SUCCESS(f"Notificaciones enviadas: {n}"))
