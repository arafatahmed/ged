from django.dispatch import Signal

# Émis dans la transaction de création d'une institution (arguments : institution).
# Les modules qui ont des référentiels par institution s'y abonnent.
institution_creee = Signal()
