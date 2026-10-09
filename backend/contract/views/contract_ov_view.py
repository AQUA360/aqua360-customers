from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from contract.models import Contract
from contract.serializers.contract_ov_serializer import ContractSerializer
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

class ContractOVView(APIView):
    queryset = Contract.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    
    def get(self, request, contract_token):
        if not contract_token:
            return Response({'error': 'Contract token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        contract = Contract.objects.filter(token=contract_token).first()
        if not contract:
            return Response({'error': 'Contract not found'}, status=status.HTTP_400_NOT_FOUND)
        
        serializer = ContractSerializer(contract)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request, contract_token):
        print("normal post")
        if not contract_token:
            return Response({'error': 'Contract token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        contract = Contract.objects.filter(token=contract_token).first()
        if not contract:
            return Response({'error': 'Contract not found'}, status=status.HTTP_400_NOT_FOUND)
        
        serializer = ContractSerializer(contract)
        return Response(serializer.data, status=status.HTTP_200_OK)