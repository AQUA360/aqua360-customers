from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from celery.result import AsyncResult

from communication.models import Communication
from communication.tasks import generate_files_task
from communication.utils.communication_service import get_uploaded_file_from_request, upload_communication_document


class CommunicationGenerateFilesViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Communication.objects.all().order_by('-created_at')
    
    def post(self, request, *args, **kwargs):
        # Check if a document is being uploaded directly using helper function
        uploaded_file = get_uploaded_file_from_request(request, 'document')
        
        # If document is provided, process it directly
        if uploaded_file:
            communication_id = request.data.get('communication')
            if not communication_id:
                return Response(
                    {"error": "El camp 'communication' és obligatori quan s'envia un document"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                communication = Communication.objects.get(id=communication_id)
            except Communication.DoesNotExist:
                return Response(
                    {"error": f"La comunicació amb ID {communication_id} no existeix"}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            try:
                # Upload document and create CommunicationFile using helper function
                comm_file = upload_communication_document(uploaded_file, communication, is_letter=False)
                
                return Response({
                    "message": "Document pujat i vinculat correctament",
                    "communication_file_id": comm_file.id,
                    "communication_id": communication.id,
                    "document_id": comm_file.file.id
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                return Response(
                    {"error": f"Error en processar el document: {str(e)}"}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Otherwise, use the existing behavior with communication_ids
        communication_ids = request.data.get('communication_ids', [])
        
        if not communication_ids:
            return Response(
                {"error": "S'ha de proporcionar 'communication_ids' o 'document' amb 'communication'"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Start the Celery task
            task = generate_files_task.delay(communication_ids)
            
            return Response({
                "message": "File generation started",
                "task_id": task.id,
                "total_communications": len(communication_ids)
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, task_id, *args, **kwargs):
        try:
            task_result = AsyncResult(task_id)
            
            if task_result.ready():
                if task_result.successful():
                    result = task_result.get()
                    progress = 100
                    task_status = 'SUCCESS'
                else:
                    result = str(task_result.result)
                    progress = 0
                    task_status = 'FAILURE'
            else:
                # For in-progress tasks
                result = None
                # Calculate progress based on number of completed subtasks
                if task_result.children:
                    completed = sum(1 for child in task_result.children if child.ready())
                    total = len(task_result.children)
                    total = total if total else 0
                    progress = int((completed / total) * 100) if total > 0 else 0
                else:
                    progress = 0
                task_status = task_result.status
            
            return Response({
                'status': task_status,
                'progress': progress,
                'result': result
            })
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)