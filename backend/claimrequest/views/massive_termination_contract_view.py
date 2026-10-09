from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django.db import transaction
from datetime import datetime
import logging

from order.models import Order, OrderType, OrderStatus
from contract.models import Contract, ContractTerminationRequest, ContractTerminationStatus, ContractTerminationType
from coredata.models import ConfigProject
from claimrequest.models import ClaimRequest

logger = logging.getLogger(__name__)

class MassiveTerminationContractViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = ClaimRequest.objects.all().order_by('-created_at')
    def post(self, request):
        try:
            # Validar dades d'entrada
            request_id = request.data.get('request_id')
            contracts = request.data.get('contracts')
            cancellation_date = request.data.get('cancellation_date')
            cancellation_reason = request.data.get('cancellation_reason')
            observations = request.data.get('observations')

            if not all([request_id, contracts, cancellation_date, cancellation_reason]):
                return Response({
                    'error': 'Falten camps obligatoris'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validar format de data
            try:
                cancellation_date = datetime.strptime(cancellation_date, '%Y-%m-%d').date()
            except ValueError:
                return Response({
                    'error': 'Format de data invàlid. Utilitzeu YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)

            
            try:
                termination_type = ContractTerminationType.objects.get(id=cancellation_reason)
            except ContractTerminationType.DoesNotExist:
                return Response({
                    'error': 'El tipus de cancel·lació no existeix'
                }, status=status.HTTP_400_BAD_REQUEST)

            
            try:
                claim_request = ClaimRequest.objects.get(id=request_id)
            except ClaimRequest.DoesNotExist:
                return Response({
                    'error': 'el ClaimRequest no existeix'
                }, status=status.HTTP_400_BAD_REQUEST)

            
            with transaction.atomic():
                try:
                    # Obtenir l'estat de cancel·lació pendent
                    pending_status = ContractTerminationStatus.objects.get(token=ConfigProject.objects.get(token='contract_termination_pending_status').value)

                    created_orders = []
                    created_terminations = []

                    # Per cada contracte, crear una petició de cancel·lació i una ordre
                    for i, contract_id in enumerate(contracts, 1):
                        try:
                            contract = Contract.objects.get(id=contract_id)
                            
                            # Comprovar si ja existeix una petició de cancel·lació per aquest contracte i claim_request
                            existing_termination = ContractTerminationRequest.objects.filter(
                                contract=contract,
                                claim_request=claim_request,
                                is_active=True
                            ).first()
                            
                            if existing_termination:
                                # Actualitzar els camps de la petició existent
                                existing_termination.type = termination_type
                                existing_termination.status = pending_status
                                existing_termination.requested_at = datetime.now()
                                #existing_termination.last_reading_at = datetime.now()
                                existing_termination.save()
                                created_terminations.append(existing_termination.id)
                                logger.info(f"Actualitzada petició de cancel·lació existent: {existing_termination.id}")
                                termination_request = existing_termination
                            else:
                                # Crear la petició de cancel·lació
                                termination_request = ContractTerminationRequest.objects.create(
                                    token=f"CTR{request_id}/{i:03d}/{contract.token}",
                                    contract=contract,
                                    person=contract.holder,
                                    claim_request=claim_request,
                                    type=termination_type,
                                    status=pending_status,
                                    requested_at=datetime.now(),
                                    #last_reading_at=datetime.now(),
                                    is_active=True
                                )
                                created_terminations.append(termination_request.id)
                                logger.info(f"Creada nova petició de cancel·lació: {termination_request.id}")

                            # Trobar les ordres de treball associades
                            associated_orders = Order.objects.filter(
                                claim_request=claim_request,
                                contract=contract,
                                is_active=True
                            )

                            print("--------------------------------")
                            print(associated_orders)
                            print("--------------------------------")

                            if associated_orders:
                                for order in associated_orders:
                                    order.contract_termination_request = termination_request
                                    order.save()

                            
                        except Exception as e:
                            logger.error(f"Error processant contracte {contract_id}: {str(e)}")
                            raise

                    return Response({
                        'message': f"S'han creat {len(created_terminations)} peticions de cancel·lació",
                        'terminations': created_terminations
                    }, status=status.HTTP_201_CREATED)
                    
                except Exception as e:
                    logger.error(f"Error dins de la transacció: {str(e)}")
                    raise

        except OrderType.DoesNotExist:
            return Response({
                'error': 'No s\'ha trobat el tipus d\'ordre de cancel·lació'
            }, status=status.HTTP_400_BAD_REQUEST)
        except OrderStatus.DoesNotExist:
            return Response({
                'error': 'No s\'ha trobat l\'estat per defecte'
            }, status=status.HTTP_400_BAD_REQUEST)
        except ContractTerminationType.DoesNotExist:
            return Response({
                'error': 'No s\'ha trobat el tipus de cancel·lació per defecte'
            }, status=status.HTTP_400_BAD_REQUEST)
        except ContractTerminationStatus.DoesNotExist:
            return Response({
                'error': 'No s\'ha trobat l\'estat de cancel·lació pendent'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Contract.DoesNotExist:
            return Response({
                'error': 'Un o més contractes no s\'han trobat'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': f'Ha ocorregut un error inesperat: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 