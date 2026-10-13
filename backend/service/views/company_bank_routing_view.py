from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from coredata.models import Bank
from service.filters.company_bank_routing_filter import CompanyBankRoutingFilter
from service.models import CompanyBank, CompanyBankRouting
from service.permissions import CompanyPermission
from service.serializers.company_bank_routing_serializer import CompanyBankRoutingSerializer


class CompanyBankRoutingViewSet(viewsets.ModelViewSet):
    """
    Mapa d'encaminament de remeses d'una empresa: a quin dels seus comptes va el
    que paga cada entitat bancària. Ho consumeix la pestanya d'encaminament de
    la fitxa d'empresa i s'aplica a
    `billing/utils/remittance_routing.py::resolve_payment_banks`.

    S'hi gestiona amb els mateixos permisos que l'empresa (`CompanyPermission`):
    és configuració de l'empresa, no una entitat a part.
    """

    queryset = CompanyBankRouting.objects.all().select_related('bank', 'company_bank', 'company')
    serializer_class = CompanyBankRoutingSerializer
    permission_classes = [IsAuthenticated, CompanyPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = CompanyBankRoutingFilter

    @action(detail=False, methods=['get'])
    def matrix(self, request):
        """
        El catàleg d'entitats bancàries amb el compte on encamina cadascuna a
        l'empresa demanada: és el que pinta la taula de la pàgina d'empresa.

        Paràmetres:
          - `company` (obligatori)
          - `only_used` (per defecte `true`): només les entitats que algun client
            fa servir de debò. De 572 entitats del catàleg, a la pràctica se'n
            fan servir unes desenes, i llistar-les totes fa la pantalla inservible.
          - `search`: per codi d'entitat, nom o BIC.
        """
        company_id = request.query_params.get('company')
        if not company_id:
            return Response(
                {"error": "Missing required parameter `company`"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        only_used = str(request.query_params.get('only_used', 'true')).upper() != 'FALSE'
        search = request.query_params.get('search') or ''

        # `PersonBank.bank` és un FK informat, així que el recompte de clients per
        # entitat surt d'un sol GROUP BY, sense haver de parsejar cap IBAN.
        banks = Bank.objects.annotate(clients=Count('person_banks'))
        if only_used:
            banks = banks.filter(clients__gt=0)
        if search:
            banks = banks.filter(
                Q(token__icontains=search) | Q(name__icontains=search) | Q(bic__icontains=search)
            )
        banks = banks.order_by('-clients', 'token')

        routings = {
            routing.bank_id: routing
            for routing in CompanyBankRouting.objects.filter(
                company_id=company_id, match_type=CompanyBankRouting.MATCH_PAYER_BANK
            )
        }

        rows = []
        for bank in banks:
            routing = routings.get(bank.id)
            rows.append({
                'bank': bank.id,
                'token': bank.token,
                'name': bank.name,
                'bic': bank.bic,
                'clients': bank.clients,
                'company_bank': routing.company_bank_id if routing else None,
                'routing': routing.id if routing else None,
                'is_active': routing.is_active if routing else True,
            })

        special = {}
        for match_type in (CompanyBankRouting.MATCH_FOREIGN, CompanyBankRouting.MATCH_DEFAULT):
            routing = CompanyBankRouting.objects.filter(
                company_id=company_id, match_type=match_type
            ).first()
            special[match_type] = {
                'routing': routing.id if routing else None,
                'company_bank': routing.company_bank_id if routing else None,
                'is_active': routing.is_active if routing else True,
            }

        company_banks = CompanyBank.objects.filter(
            company_id=company_id, is_active=True
        ).select_related('bank').order_by('-is_default', 'id')

        # Compte on acabarà tot el que no estigui assignat. Es demana a la
        # mateixa funció que fa servir la generació de la remesa, perquè el
        # comptador de la pantalla i el repartiment real no puguin divergir.
        from billing.utils.remittance_routing import get_company_fallback_banks

        fallback_bank_id, fallback_is_explicit = get_company_fallback_banks(
            [int(company_id)]
        ).get(int(company_id), (None, False))
        effective_default = special[CompanyBankRouting.MATCH_DEFAULT]['company_bank'] or fallback_bank_id

        return Response({
            'company': int(company_id),
            'count': len(rows),
            'banks': rows,
            'special': special,
            'effective_default': effective_default,
            # Cert quan el compte per defecte l'ha triat algú (fila `default` del
            # mapa o `CompanyBank.is_default`) i no és el primer de la llista.
            'effective_default_is_explicit': bool(
                special[CompanyBankRouting.MATCH_DEFAULT]['company_bank']
            ) or fallback_is_explicit,
            'company_banks': [
                {
                    'id': company_bank.id,
                    'iban': company_bank.iban,
                    'bank_name': company_bank.bank.name if company_bank.bank else None,
                    'is_default': company_bank.is_default,
                    'is_sepa': company_bank.is_sepa,
                }
                for company_bank in company_banks
            ],
        })

    @action(detail=False, methods=['post'])
    def bulk(self, request):
        """
        Assigna en bloc unes quantes entitats a un compte, o les desassigna.

        Cos: `{company, company_bank, banks: [ids]}`. Amb `company_bank` a null
        s'esborren les files d'aquelles entitats (tornen al compte per defecte).
        Sense això, configurar 70 entitats vol dir 70 peticions.
        """
        company_id = request.data.get('company')
        company_bank_id = request.data.get('company_bank')
        bank_ids = request.data.get('banks') or []

        if not company_id:
            return Response(
                {"error": "Missing required field `company`"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not bank_ids:
            return Response(
                {"error": "Missing required field `banks`"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not company_bank_id:
            deleted, _ = CompanyBankRouting.objects.filter(
                company_id=company_id,
                bank_id__in=bank_ids,
                match_type=CompanyBankRouting.MATCH_PAYER_BANK,
            ).delete()
            return Response({"deleted": deleted}, status=status.HTTP_200_OK)

        if not CompanyBank.objects.filter(id=company_bank_id).exists():
            return Response(
                {"error": "Unknown `company_bank`"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = 0
        created = 0
        for bank_id in bank_ids:
            _, was_created = CompanyBankRouting.objects.update_or_create(
                company_id=company_id,
                bank_id=bank_id,
                match_type=CompanyBankRouting.MATCH_PAYER_BANK,
                defaults={'company_bank_id': company_bank_id, 'is_active': True},
            )
            created += 1 if was_created else 0
            updated += 0 if was_created else 1

        return Response({"created": created, "updated": updated}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def set_bank_name(self, request):
        """
        Canvia el nom d'una entitat del catàleg (`coredata.Bank`) des de la
        pàgina d'encaminament.

        El catàleg ve d'una importació i hi ha entitats molt usades sense nom
        (p. ex. 0182), que a la taula surten com a files mudes i fan la
        configuració endevinalla. Es fa aquí, amb els permisos d'empresa, per no
        obligar a tenir permisos de persones només per posar-hi un nom.

        Cos: `{bank, name}`.
        """
        bank_id = request.data.get('bank')
        name = (request.data.get('name') or '').strip()

        if not bank_id:
            return Response(
                {"error": "Missing required field `bank`"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bank = Bank.objects.filter(id=bank_id).first()
        if not bank:
            return Response({"error": "Unknown `bank`"}, status=status.HTTP_404_NOT_FOUND)

        bank.name = name or None
        bank.save(update_fields=['name', 'updated_at'])

        return Response(
            {'bank': bank.id, 'token': bank.token, 'name': bank.name},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['post'])
    def set_special(self, request):
        """
        Desa les dues files especials del mapa: `foreign` (IBAN no espanyol) i
        `default` (la resta, i els rebuts sense IBAN).

        Cos: `{company, match_type, company_bank}`. Amb `company_bank` a null
        s'esborra la fila.
        """
        company_id = request.data.get('company')
        match_type = request.data.get('match_type')
        company_bank_id = request.data.get('company_bank')

        if not company_id:
            return Response(
                {"error": "Missing required field `company`"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if match_type not in (CompanyBankRouting.MATCH_FOREIGN, CompanyBankRouting.MATCH_DEFAULT):
            return Response(
                {"error": "`match_type` must be `foreign` or `default`"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not company_bank_id:
            deleted, _ = CompanyBankRouting.objects.filter(
                company_id=company_id, match_type=match_type
            ).delete()
            return Response({"deleted": deleted}, status=status.HTTP_200_OK)

        routing, created = CompanyBankRouting.objects.update_or_create(
            company_id=company_id,
            match_type=match_type,
            defaults={'company_bank_id': company_bank_id, 'bank_id': None, 'is_active': True},
        )
        return Response(
            CompanyBankRoutingSerializer(routing).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
