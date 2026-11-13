from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from customers.deploy_info import get_deploy_info, with_deploy_date


class FrontendDeployInfoSerializer(serializers.Serializer):
    """El que el frontend sap de si mateix (el seu `/deploy-info.json`)."""

    release = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    commit = serializers.RegexField(r"^[0-9a-fA-F]{0,40}$", required=False, allow_blank=True, default="")
    commit_full = serializers.RegexField(r"^[0-9a-fA-F]{0,40}$", required=False, allow_blank=True, default="")
    branch = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    built_at = serializers.CharField(max_length=40, required=False, allow_blank=True, allow_null=True, default=None)
    source = serializers.ChoiceField(choices=["build", "deploy", "git", "unknown"], required=False, default="build")


class DeployInfoView(APIView):
    """Versió i data del desplegament del backend i del frontend d'aquest client.

    - GET: la del backend que s'està executant.
    - POST: el frontend hi envia la seva (versió i commit) i rep la data en què
      es va desplegar, que surt de l'historial (`coredata.DeployRecord`).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        info = get_deploy_info(refresh=request.query_params.get('refresh') == 'true')
        return Response(with_deploy_date("backend", info))

    def post(self, request):
        serializer = FrontendDeployInfoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        info = {**serializer.validated_data, "component": "frontend"}
        info["deployed_at"] = info["built_at"]
        return Response(with_deploy_date("frontend", info))
