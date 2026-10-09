from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from communication.models import Communication, CommunicationProcessStatus, CommunicationStatus, CommunicationProcess
from communication.tasks import send_communications_task
from coredata.models import ConfigProject


class ManageSendCommunicationsViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Communication.objects.all().order_by('-created_at')
    def post(self, request, *args, **kwargs):
        communication_ids = request.data.get('communication_ids', [])
        process_id = request.data.get('process_id', None)

        try:
            process = None
            communications = []
            if process_id:
                process = CommunicationProcess.objects.get(id=process_id)
                process_sent = CommunicationProcessStatus.objects.get(token=ConfigProject.objects.get(token='communication_process_status_current_token').value)
                process.status = process_sent
                process.save()
                communications = process.communications.all()
            else:
                communications = Communication.objects.filter(id__in=communication_ids)
            com_status_sent = CommunicationStatus.objects.get(token=ConfigProject.objects.get(token='communication_status_sent_token').value)
            
            coms_without_email = communications.filter(used_email=None).filter(used_email='').count()
            coms_without_phone = communications.filter(used_phones=None).filter(used_phones='').count()
            
            
            # Start the Celery task
            task = send_communications_task.delay(
                process_id=process_id,
                communication_ids=communication_ids if not process_id else None,
            )
            
            return Response({
                "message": "Communications processing started",
                "task_id": task.id,
                "stats": {
                    "total_communications": communications.count(),
                    "without_email": coms_without_email,
                    "without_phone": coms_without_phone
                }
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    
    def get(self, request, *args, **kwargs):
        try:
            print("inside get")
            process_id = kwargs.get('id')
            process = CommunicationProcess.objects.get(id=process_id)
            
            # Build callback URL before passing to Celery task
            only_returned = request.query_params.get('only_returned') == 'true'

            # Start the Celery task
            print("before sending comss")
            task = send_communications_task.delay(
                process_id=process_id,
                only_returned=only_returned
            )
            
            return Response({
                "message": "Communications processing started",
                "task_id": task.id,
                "total_communications": process.communications.count()
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            print(f"error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        