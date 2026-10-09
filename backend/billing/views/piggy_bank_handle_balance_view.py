from django.apps import apps
from django.db.models import Q
from rest_framework import status
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django.utils import timezone
from contract.models import PiggyBank
from contract.permissions import ContractPermission
from coredata.utils.name_utils import generate_token

class PiggyBankHandleBalanceViewSet(generics.ListAPIView):

    permission_classes = [IsAuthenticated, ContractPermission]
    queryset = PiggyBank.objects.all().order_by('-created_at')
    
    def post(self, request):
        try:
            piggy_bank_id = request.query_params.get('id')
            related_piggy_banks = request.data.get('related_piggy_banks')
            total_to_transfer = request.data.get('total_to_transfer')
            total_incoming = request.data.get('total_incoming')
            total_outgoing = request.data.get('total_outgoing')
            is_person = request.data.get('is_person', False)
            user = request.user
            
            print("related_piggy_banks", related_piggy_banks)
            print("total_to_transfer", total_to_transfer)
            print("is_person", is_person)
            print("piggy_bank_id", piggy_bank_id)
            
            calculated_total_to_transfer = 0
            
            if is_person:
                PiggyBank = apps.get_model('coredata', 'PersonPiggyBank')
                PiggyMovement = apps.get_model('coredata', 'PersonPiggyBankMovement')
                RelatedPiggyBank = apps.get_model('contract', 'PiggyBank')
                PiggyBankMovement = apps.get_model('contract', 'PiggyBankMovement')
            else:
                PiggyBank = apps.get_model('contract', 'PiggyBank')
                PiggyMovement = apps.get_model('contract', 'PiggyBankMovement')
                RelatedPiggyBank = apps.get_model('coredata', 'PersonPiggyBank')
                PiggyBankMovement = apps.get_model('coredata', 'PersonPiggyBankMovement')
            piggy_bank = PiggyBank.objects.get(id=piggy_bank_id)
            
            
            ordered_related_piggy_banks = sorted(
                related_piggy_banks,
                key=lambda x: x.get("is_giving", False),
                reverse=True,
            )
            for related_piggy_bank in ordered_related_piggy_banks:
                
                related_piggy_instance = RelatedPiggyBank.objects.get(id=related_piggy_bank.get("id"))
                positive_amount = related_piggy_bank.get("is_giving", False)
                amount_to_transfer = related_piggy_bank.get("amount_to_transfer", 0) * (1 if positive_amount else -1)
                
                related_piggy_instance.amount = float(related_piggy_instance.amount) + float(amount_to_transfer)
                related_piggy_instance.save()
                
                new_movement = PiggyBankMovement(
                    token=generate_token(PiggyBankMovement),
                    amount=amount_to_transfer,
                    is_positive=positive_amount,
                    movement_date=timezone.now(),
                    user=user,
                )
                if is_person:
                    new_movement.piggy_bank = related_piggy_instance
                else:
                    new_movement.person_piggy_bank = related_piggy_instance
                new_movement.save()
                
                calculated_total_to_transfer = float(calculated_total_to_transfer) - float(amount_to_transfer)
            
            if float(calculated_total_to_transfer) != float(total_to_transfer):
                print("calculated_total_to_transfer != total_to_transfer")
            print("calculated_total_to_transfer", calculated_total_to_transfer)
            print("total_to_transfer", total_to_transfer)
            
            if (float(piggy_bank.amount) + float(total_to_transfer)) < 0:
                print("total to transfer out of bounds")
            piggy_bank.amount = float(piggy_bank.amount) + float(total_to_transfer)
            piggy_bank.save()
            
            if total_incoming != 0:
                new_movement = PiggyMovement(
                    token=generate_token(PiggyMovement),
                    amount=total_incoming,
                    is_positive=True,
                    movement_date=timezone.now(),
                    user=user,
                )
                if is_person:
                    new_movement.person_piggy_bank = piggy_bank
                else:
                    new_movement.piggy_bank = piggy_bank
                new_movement.save()
            if total_outgoing != 0:
                new_movement = PiggyMovement(
                    token=generate_token(PiggyMovement),
                    amount=-total_outgoing,
                    is_positive=False,
                    movement_date=timezone.now(),
                    user=user,
                )
                if is_person:
                    new_movement.person_piggy_bank = piggy_bank
                else:
                    new_movement.piggy_bank = piggy_bank
                new_movement.save()
            
            return Response({"message": "Inbetween handled"}, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Error getting related data: {e}")
            return Response({"error": "Error getting related data"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
