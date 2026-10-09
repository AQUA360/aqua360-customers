from django.http import Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from documentmanager.tasks import generic_export_task
from documentmanager.utils.export_jobs import enqueue_export, export_job_response
from documentmanager.utils.export_registry import get_export_config


class GenericExportView(APIView):
    """
    Vista d'exportació única per a qualsevol entitat registrada a
    documentmanager.utils.export_registry.EXPORT_REGISTRY.

    Muntar-la per recurs amb `GenericExportView.as_view(entity="invoice")`
    des de l'urls.py de l'app corresponent (ex: `billing/invoice/export/`).

    Contracte de resposta (igual per a totes les entitats):
        202 {"task_id", "export_job_id", "status": "pending", "message"}
        -> GET /documentmanager/export-job/{export_job_id}/ (cua de descàrregues de l'usuari)
           o, com abans, GET /task-progress/{task_id}/
           SUCCESS: {"state", "result": {"document_id", "document_name"}}

    `export_name` (query param, opcional) és el nom que es mostra al panell de
    descàrregues; si no arriba, s'usa el nom del model.
    """
    entity = None

    def get_config(self):
        config = get_export_config(self.entity)
        if config is None:
            raise Http404(f"Unknown export entity: {self.entity}")
        return config

    def get_permissions(self):
        try:
            config = self.get_config()
        except Http404:
            return [IsAuthenticated()]
        return [permission() for permission in config.permission_classes]

    def get_queryset(self):
        return self.get_config().queryset()

    def post(self, request, *args, **kwargs):
        # Assegura que l'entitat existeix i llença 404 abans de despatxar la task.
        config = self.get_config()
        query_params = request.query_params.dict()
        name = query_params.pop("export_name", None) or str(config.queryset().model._meta.verbose_name_plural).capitalize()
        job = enqueue_export(
            request, generic_export_task,
            kind=f"generic:{self.entity}", name=name,
            args=[self.entity, query_params], params=query_params,
        )
        return Response(export_job_response(job), status=status.HTTP_202_ACCEPTED)
