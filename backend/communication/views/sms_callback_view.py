from rest_framework.permissions import AllowAny, IsAuthenticated, DjangoModelPermissions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView




class SmsCallbackView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        try:
            user = request.user
            print(user)
            print(user.__dict__)
            
            data = request.data
            print(data)
            
            return Response({
                "ok": "ok"
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        