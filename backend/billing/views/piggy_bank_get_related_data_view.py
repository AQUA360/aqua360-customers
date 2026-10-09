from django.db.models import Q
from rest_framework import status
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response

from contract.models import Contract, PiggyBank
from contract.permissions import ContractPermission
from coredata.models import Person, PersonPiggyBank
from contract.serializers.piggy_bank_serializer import PiggyBankSerializer
from coredata.serializers import PersonPiggyBankSerializer

class PiggyBankGetRelatedDataViewSet(generics.ListAPIView):

    permission_classes = [IsAuthenticated, ContractPermission]
    queryset = PiggyBank.objects.all().order_by('-created_at')
    
    def get(self, request):
        try:
            piggy_bank_id = request.query_params.get('id')
            is_person = request.query_params.get('is_person', 'false').lower() == 'true'
            print("piggy_bank_id", piggy_bank_id)
            print("is_person", is_person)
            contracts = []
            persons = []
            related_piggy_banks = []
           
            if is_person:
                piggy_bank = PersonPiggyBank.objects.get(id=piggy_bank_id)
                person = Person.objects.get(piggy_bank__id=piggy_bank_id)
                serialized_piggy_bank = PersonPiggyBankSerializer(piggy_bank).data
                contracts = Contract.objects.filter(
                    Q(holder=person) | Q(tenant=person) | Q(owner=person)
                )
                related_piggy_banks = PiggyBank.objects.filter(contracts__in=contracts).distinct()
                serialized_related_piggy_banks = PiggyBankSerializer(related_piggy_banks, many=True).data
            else:
                piggy_bank = PiggyBank.objects.get(id=piggy_bank_id)
                contract = Contract.objects.get(piggy_bank__id=piggy_bank_id)
                serialized_piggy_bank = PiggyBankSerializer(piggy_bank).data
                persons.append(contract.holder)
                if contract.tenant:
                    persons.append(contract.tenant)
                if contract.owner:
                    persons.append(contract.owner)
                related_piggy_banks = PersonPiggyBank.objects.filter(person__in=persons).distinct()
                serialized_related_piggy_banks = PersonPiggyBankSerializer(related_piggy_banks, many=True).data
            
            return Response({
                "piggy_bank": serialized_piggy_bank,
                "related_piggy_banks": serialized_related_piggy_banks,
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Error getting related data: {e}")
            return Response({"error": "Error getting related data"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
