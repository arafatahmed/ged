"""Client minimal du démon ClamAV (clamd), protocole INSTREAM sur TCP.

Le flux est envoyé par morceaux préfixés de leur longueur (4 octets, ordre
réseau), terminé par un morceau vide. Réponses : « stream: OK »,
« stream: <signature> FOUND » ou « ... ERROR ».

Sans hôte configuré (développement uniquement : la production l'exige), aucun
antivirus n'analyse les fichiers et l'événement d'audit le signale.
"""

import socket
import struct
from dataclasses import dataclass

from django.conf import settings


class AntivirusIndisponible(Exception):
    """L'antivirus n'a pas pu rendre de verdict : le fichier reste en attente."""


@dataclass(frozen=True)
class Verdict:
    sain: bool
    signature: str = ""
    trop_volumineux: bool = False


class ClientClamd:
    nom = "clamav"

    def __init__(self, hote, port, delai):
        self.hote = hote
        self.port = port
        self.delai = delai

    def analyser(self, morceaux):
        try:
            with socket.create_connection((self.hote, self.port), timeout=self.delai) as connexion:
                connexion.sendall(b"zINSTREAM\0")
                try:
                    for morceau in morceaux:
                        if morceau:
                            connexion.sendall(struct.pack("!L", len(morceau)) + morceau)
                    connexion.sendall(struct.pack("!L", 0))
                except (BrokenPipeError, ConnectionResetError):
                    # clamd coupe la connexion quand la limite StreamMaxLength est dépassée ;
                    # sa réponse reste lisible.
                    pass
                reponse = self._lire(connexion)
        except OSError as erreur:
            raise AntivirusIndisponible(str(erreur)) from erreur
        return self.interpreter(reponse)

    @staticmethod
    def _lire(connexion):
        reponse = b""
        while not reponse.endswith(b"\0"):
            morceau = connexion.recv(4096)
            if not morceau:
                break
            reponse += morceau
        return reponse.rstrip(b"\0").decode("utf-8", "replace").strip()

    @staticmethod
    def interpreter(reponse):
        if reponse.endswith("OK"):
            return Verdict(sain=True)
        if reponse.endswith("FOUND"):
            signature = reponse.removeprefix("stream:").removesuffix("FOUND").strip()
            return Verdict(sain=False, signature=signature)
        if "size limit exceeded" in reponse.lower():
            return Verdict(sain=False, trop_volumineux=True)
        raise AntivirusIndisponible(reponse or "réponse vide")


class SansAntivirus:
    """Développement sans ClamAV : lit le flux (pour l'empreinte) sans l'analyser."""

    nom = "aucun"

    def analyser(self, morceaux):
        for _morceau in morceaux:
            pass
        return Verdict(sain=True)


def client():
    if settings.GED_ANTIVIRUS_HOTE:
        return ClientClamd(settings.GED_ANTIVIRUS_HOTE, settings.GED_ANTIVIRUS_PORT, settings.GED_ANTIVIRUS_DELAI)
    return SansAntivirus()
