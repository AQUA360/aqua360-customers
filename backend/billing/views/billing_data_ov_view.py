from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from billing.models import Billing
from contract.models import Contract
from billing.serializers.billing_data_ov_serializer import BillingDataOVSerializer
from coredata.models import PersonContact

class BillingDataOVView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Contract.objects.all().order_by('-created_at')
    def get(self, request, contract_token):
        if not contract_token:
            return Response({'error': 'Contract token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        contract = Contract.objects.filter(token=contract_token).first()
        if not contract:
            return Response({'error': 'Contract not found'}, status=status.HTTP_400_NOT_FOUND)
        
        serializer = BillingDataOVSerializer(contract)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    
    def post(self, request, contract_token):
        if not contract_token:
            return Response({'error': 'Contract token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        contract = Contract.objects.filter(token=contract_token).first()
        if not contract:
            return Response({'error': 'Contract not found'}, status=status.HTTP_400_NOT_FOUND)
        
        email = request.data.get('email')
        paper_invoice = request.data.get('paper_invoice')
        invoice_language = request.data.get('invoice_language')
        phone1 = request.data.get('phone1')
        phone2 = request.data.get('phone2')

        try:
            if invoice_language and invoice_language in dict(settings.LANGUAGES):
                contract.language = invoice_language
                contract.save()

            if isinstance(paper_invoice, bool):
                if paper_invoice:
                    contract.communication_type = 'PAPER'
                else:
                    contract.communication_type = 'DIGITAL'
            else:
                if paper_invoice.lower() == 'true':
                    contract.communication_type = 'PAPER'
                else:
                    contract.communication_type = 'DIGITAL'
                    
            try:
                contract.person_contact_email.email = email     
                contract.person_contact_email.save()     
            except Exception as e:
                print("Error updating email: ", e)
            
            # WORKING ON BOTH CONTACT AND SMS FOR NOW
            if (phone1 and phone1 != '') or (phone2 and phone2 != ''):
                contract.contacts.clear()
                contract.person_contact_sms.clear()
                total_contacts = PersonContact.objects.filter(person=contract.holder).count() + 1
                
                if phone1 and phone1 != '':
                    person_contact1, created1 = PersonContact.objects.get_or_create(
                        person=contract.holder,  
                        phone=phone1,
                        role='HOLDER',
                    )
                    if not created1:
                        person_contact1.is_active = True
                    else:
                        total_contacts += 1
                        person_contact1.token = f"{contract.holder.token}_{total_contacts}"
                    person_contact1.save()
                    contract.contacts.add(person_contact1)
                    contract.person_contact_sms.add(person_contact1)
                    
                if phone2 and phone2 != '':
                    person_contact2, created2 = PersonContact.objects.get_or_create(
                        person=contract.holder,  
                        phone=phone2,
                        role='HOLDER',
                    )
                    if not created2:
                        person_contact2.is_active = True
                    else:
                        total_contacts += 1
                        person_contact2.token = f"{contract.holder.token}_{total_contacts}"
                    person_contact2.save()
                    contract.contacts.add(person_contact2)
                    contract.person_contact_sms.add(person_contact2)
                contract.save()
            
        except Exception as e:
            print("Error updating contract: ", e)
            return Response({'error': 'Error updating contract'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        serializer = BillingDataOVSerializer(contract)
        return Response(serializer.data, status=status.HTTP_200_OK)