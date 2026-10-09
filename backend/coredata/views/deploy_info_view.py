from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from customers.deploy_info import get_deploy_info


class DeployInfoView(APIView):
    """Data i commit del deploy del backend que s'està executant.

    El NavSidebar del frontend ho combina amb el seu propi `/deploy-info.json`
    per mostrar la data del deploy i, en passar-hi el ratolí, el commit de
    frontend i el de backend.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_deploy_info(refresh=request.query_params.get('refresh') == 'true'))
