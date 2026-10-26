import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from documents import antivirus
from documents.analyse import analyser_en_attente, nettoyer_quarantaine

NETTOYAGE_SECONDES = 3600


class Command(BaseCommand):
    help = (
        "Analyse les fichiers en quarantaine (antivirus, empreinte, type réel) puis les publie ou les refuse. "
        "Avec --boucle, tourne en continu et nettoie la quarantaine toutes les heures."
    )

    def add_arguments(self, parser):
        parser.add_argument("--boucle", action="store_true", help="Tourner en continu (service « analyseur »).")
        parser.add_argument("--intervalle", type=float, default=2.0, help="Pause entre deux passes, en secondes.")

    def handle(self, *args, boucle=False, intervalle=2.0, **options):
        client = antivirus.client()
        if client.nom == "aucun":
            self.stderr.write(
                self.style.WARNING("Aucun antivirus configuré (GED_ANTIVIRUS_HOTE) : développement seulement.")
            )
        if not boucle:
            self.stdout.write(f"{analyser_en_attente(client)} fichier(s) analysé(s).")
            return
        self.stdout.write(f"Analyseur démarré (antivirus : {client.nom}).")
        dernier_nettoyage = None
        while True:
            try:
                close_old_connections()
                if dernier_nettoyage is None or time.monotonic() - dernier_nettoyage > NETTOYAGE_SECONDES:
                    effaces = nettoyer_quarantaine()
                    if effaces:
                        self.stdout.write(f"Quarantaine : {effaces} objet(s) orphelin(s) effacé(s).")
                    dernier_nettoyage = time.monotonic()
                traites = analyser_en_attente(client)
                if traites:
                    self.stdout.write(f"{traites} fichier(s) analysé(s).")
            except antivirus.AntivirusIndisponible as erreur:
                self.stderr.write(f"Antivirus indisponible, nouvel essai plus tard : {erreur}")
                time.sleep(max(intervalle, 10))
            except Exception as erreur:
                # Le service doit survivre à une base ou un stockage momentanément absents.
                self.stderr.write(f"Erreur de l'analyseur : {erreur!r}")
                time.sleep(max(intervalle, 10))
            time.sleep(intervalle)
