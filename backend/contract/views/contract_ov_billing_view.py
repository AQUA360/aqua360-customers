from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from billing.models import GeneralPayment
from contract.models import Contract, PaymentType
from contract.serializers.contract_ov_serializer import ContractSerializer
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from coredata.models import Bank, ConfigProject, Country, PersonBank
from coredata.utils.iban_validator_utils import get_spanish_bank_code_candidates

class ContractOVBillingView(APIView):
    queryset = Contract.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    
    def post(self, request, contract_token):
        if not contract_token:
            return Response({'error': 'Contract token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        contract = Contract.objects.filter(token=contract_token).first()
        if not contract:
            return Response({'error': 'Contract not found'}, status=status.HTTP_400_NOT_FOUND)
        
        nif = request.data.get('nif')
        iban = request.data.get('iban').replace(' ', '')
        payment_type = PaymentType.objects.get(token = ConfigProject.objects.get(token='direct_debit_token').value)
        payment = contract.payment
        total_payments = PersonBank.objects.filter(person=contract.holder).count() + 1
        new_payment = None
        if payment and payment.IBAN:
            if payment.IBAN.iban and payment.IBAN.iban.upper() == iban.upper():
                new_payment = payment
        
        if not new_payment:
            country_code = iban[:2]
            country = Country.objects.filter(iso_code=country_code).first()
            bank = None
            #TODO: Add other countries if needed (same 4 digits for bank code?)
            if country_code == "ES":
                bank_code = f"{int(iban[4:8]):04d}"
                bank = Bank.objects.filter(token__in=get_spanish_bank_code_candidates(bank_code)).first()
                if not bank:
                    print(f"Bank {bank_code} not found")
                    
            new_person_bank, created = PersonBank.objects.get_or_create(
                person=contract.holder,
                iban=iban,
                country=country,
                bank=bank,
                role="HOLDER",
                dni=nif,
                #TODO: SWIFT INCOMPLETE IN BANK
            )
            if created:
                new_person_bank.token=f"{contract.holder.token}_{total_payments+1}"
                new_person_bank.name=f"{contract.holder.name} {contract.holder.surname if contract.holder.surname else ''}"
                new_person_bank.save()
            
            new_payment, payment_created = GeneralPayment.objects.get_or_create(
                type=payment_type,
                IBAN=new_person_bank,
            )
            if payment_created:
                new_payment.token=f"{contract.token}_{new_payment.token}"
                new_payment.save()
        contract.payment = new_payment
        contract.save()
        serializer = ContractSerializer(contract)
        return Response(serializer.data, status=status.HTTP_200_OK)