from django.http import Http404
from rest_framework.generics import RetrieveAPIView

from .serializers import InstitutionSerializer


class InstitutionCouranteView(RetrieveAPIView):
    """Institution de l'utilisateur connecté."""

    serializer_class = InstitutionSerializer

    def get_object(self):
        institution = self.request.user.institution
        if institution is None:
            raise Http404
        return institution
