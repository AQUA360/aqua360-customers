from contract.models import (
    ContractRequestType,
    Contract,
    ContractStatus,
    ContractPriceRate,
    PiggyBankMovement,
)
from service.models import (
    Cluster,
    ClusterNozzle,
    Connection,
    Exploitation,
    SupplyPoint,
    SupplyPointStatus,
    Meter,
    Property,
    Company,
    CompanyBank
)
from order.models import Order
from coredata.models import (
    Address,
    PersonBank,
    PostalCode,
    PersonAddress,
    Person,
    ConfigProject,
    Country,
    Province,
    City,
    PersonPiggyBankMovement,
)
from pricing.models import PriceRate, BillingRange
from billing.models import (
    Invoice,
    InvoiceSequence,
    InvoiceStatus,
    Payment,
    PaymentMovement,
    PaymentStatus,
    Reading,
)
from django.db.models import Count, Q, F, Exists, OuterRef, Prefetch, Subquery, Max
from django.db.models.functions import Length
from watchdog.aca_config import check_aca_article_code_issues, check_aca_configuration_issues
from watchdog.persons_without_contact import (
    ACTIVE_CONTRACT_CHECK_NAME,
    ZOMBIE_PERSONS_CHECK_NAME,
)
from watchdog.management.commands.watchdog_variable_types import check_condition_variable_type_references
from django.utils import timezone
from notification.models import Incident


def find_desynced_invoice_sequences():
    """
    Retorna seqüències de serie_final (prefix amb '/') on last_number
    queda per sota del número màxim ja assignat a Invoice.serie_final.

    Cada element: {prefix, sequence, last_number, max_number, max_serie_final}
    """
    desynced = []
    for seq in InvoiceSequence.objects.filter(prefix__contains="/").order_by("prefix"):
        max_serie = (
            Invoice.objects.filter(serie_final__startswith=seq.prefix + "/")
            .exclude(serie_final__isnull=True)
            .exclude(serie_final="")
            .aggregate(max_serie=Max("serie_final"))["max_serie"]
        )
        if not max_serie:
            continue
        try:
            max_number = int(max_serie.split("/")[-1])
        except (ValueError, IndexError):
            continue
        if seq.last_number < max_number:
            desynced.append(
                {
                    "prefix": seq.prefix,
                    "sequence": seq,
                    "last_number": seq.last_number,
                    "max_number": max_number,
                    "max_serie_final": max_serie,
                }
            )
    return desynced


class DataIntegrityService:

    def check_meters_duplicate_tokens(self):
        """
        Check for Meter records with duplicate tokens.
        """
        issues = []
        duplicates = (
            Meter.objects.values("token")
            .annotate(token_count=Count("token"))
            .filter(token_count__gt=1)
        )

        for entry in duplicates:
            token = entry["token"]
            count = entry["token_count"]
            issues.append(
                f"El token del comptador '{token}' està duplicat {count} vegades"
            )

        return issues

    def check_active_contracts_sharing_meter(self):
        """
        Check for Meters that are associated with more than one Active Contract (via SupplyPoints).
        """
        issues = []

        try:
            config = ConfigProject.objects.get(token="contract_active_token")
            active_status_token = config.value
            active_status = ContractStatus.objects.get(token=active_status_token)
        except (ConfigProject.DoesNotExist, ContractStatus.DoesNotExist):
            return [
                "Configuration error: 'contract_active_token' or corresponding ContractStatus not found."
            ]

        # Find Meters linked to more than one unique active Contract
        # We traverse: Meter -> SupplyPoint -> Contract
        duplicates = (
            Meter.objects.filter(supply_points__contracts__status=active_status)
            .annotate(
                active_contract_count=Count("supply_points__contracts", distinct=True)
            )
            .filter(active_contract_count__gt=1)
        )

        for record in duplicates:
            issues.append(
                f"El comptador ID {record.id} ({record.code}) està associat amb {record.active_contract_count} Contractes Actius"
            )

        return issues

    def check_active_contracts_without_price_rate(self):
        """
        Contractes actius sense cap ContractPriceRate amb PriceRate associada (FK no nul·la).
        """
        issues = []
        try:
            config = ConfigProject.objects.get(token="contract_active_token")
            active_status_token = config.value
            active_status = ContractStatus.objects.get(token=active_status_token)
        except (ConfigProject.DoesNotExist, ContractStatus.DoesNotExist):
            return [
                "Configuration error: 'contract_active_token' or corresponding ContractStatus not found."
            ]

        invalid = (
            Contract.objects.filter(status=active_status)
            .annotate(
                _priced=Count(
                    "price_rates",
                    filter=Q(price_rates__price_rate__isnull=False),
                    distinct=True,
                )
            )
            .filter(_priced=0)
            .order_by("id")
        )

        for record in invalid:
            token = record.token or ""
            issues.append(
                f"Contract actiu ID {record.id} ({token}) no té cap PriceRate associada "
                f"(M2M price_rates buida o tots els ContractPriceRate sense price_rate)."
            )

        return issues

    def check_digital_contracts_without_email(self):
        """
        Check for Contract records with communication_type='DIGITAL' that have no email contact.
        """
        issues = []
        # Check if person_contact_email is NULL OR the related PersonContact has no email
        invalid_records = Contract.objects.filter(communication_type="DIGITAL").filter(
            Q(person_contact_email__isnull=True)
            | Q(person_contact_email__email__isnull=True)
            | Q(person_contact_email__email="")
        )

        for record in invalid_records:
            issues.append(
                f"Contract ID {record.id} ({record.token}) is DIGITAL but has no email contact"
            )

        return issues

    def check_active_contracts_last_reading_meter_mismatch(self):
        """
        Per cada contracte actiu, comprova que l'última Reading tingui un Meter
        vinculat a un SupplyPoint del contracte (Meter -> SupplyPoint -> Contract.supply_points).
        """
        issues = []

        try:
            config = ConfigProject.objects.get(token="contract_active_token")
            active_status_token = config.value
            active_status = ContractStatus.objects.get(token=active_status_token)
        except (ConfigProject.DoesNotExist, ContractStatus.DoesNotExist):
            return [
                "Configuration error: 'contract_active_token' or corresponding ContractStatus not found."
            ]

        last_reading_subq = (
            Reading.objects.filter(contract_id=OuterRef("pk"))
            .order_by("-reading_date", "-id")
            .values("pk")[:1]
        )

        last_reading_ids = (
            Contract.objects.filter(status=active_status)
            .annotate(_last_reading_id=Subquery(last_reading_subq))
            .filter(_last_reading_id__isnull=False)
            .values_list("_last_reading_id", flat=True)
        )

        meter_linked_to_contract = SupplyPoint.objects.filter(
            meter_id=OuterRef("meter_id"),
            contracts__id=OuterRef("contract_id"),
        )

        mismatched = (
            Reading.objects.filter(id__in=last_reading_ids)
            .filter(
                Q(meter__isnull=True)
                | ~Exists(meter_linked_to_contract)
            )
            .select_related("meter", "contract", "supply_point")
            .order_by("contract_id", "id")
        )

        for reading in mismatched:
            contract = reading.contract
            contract_token = (contract.token if contract else None) or ""
            reading_info = (
                f"Reading ID {reading.id}, data {reading.reading_date or 'N/A'}, "
                f"valor {reading.reading_value if reading.reading_value is not None else 'N/A'}, "
                f"supply_point_id={reading.supply_point_id}"
            )

            if reading.meter_id is None:
                issues.append(
                    f"Contract ID {reading.contract_id} ({contract_token}): "
                    f"última lectura sense Meter. {reading_info}"
                )
            else:
                meter = reading.meter
                meter_code = (meter.code if meter else None) or ""
                issues.append(
                    f"Contract ID {reading.contract_id} ({contract_token}): "
                    f"última lectura amb Meter ID {reading.meter_id} ({meter_code}) "
                    f"no vinculat a cap SupplyPoint del contracte. {reading_info}"
                )

        return issues

    def check_readings_without_meter(self):
        """
        Detecta lectures actives sense comptador associat (meter_id NULL)
        que no estan marcades com a lectura de control.
        """
        issues = []

        queryset = (
            Reading.objects.filter(
                is_active=True,
                is_control=False,
                meter__isnull=True,
            )
            .select_related('contract', 'supply_point')
            .order_by('id')
        )

        total = queryset.count()
        if total == 0:
            return issues

        max_display = 50
        for reading in queryset[:max_display]:
            contract_part = (
                f", Contracte ID {reading.contract_id}" if reading.contract_id else ""
            )
            sp_part = (
                f", SupplyPoint ID {reading.supply_point_id}"
                if reading.supply_point_id
                else ""
            )
            issues.append(
                f"Lectura ID {reading.id} sense meter_id "
                f"(data {reading.reading_date or 'N/A'}{contract_part}{sp_part})"
            )

        if total > max_display:
            issues.append(
                f"... i {total - max_display} lectures més sense meter_id (total: {total})"
            )

        issues.append("")
        issues.append("Recomanació (watchdog): associa el comptador del punt de subministrament o marca com a control:")
        issues.append("  python manage.py watchdog_fix_readings_without_meter --dry-run")
        issues.append("  python manage.py watchdog_fix_readings_without_meter")

        return issues

    def check_future_readings(self):
        """
        Check for Reading records with reading_date > NOW().
        """
        issues = []
        now = timezone.now().date()
        invalid_records = Reading.objects.filter(reading_date__gt=now)

        for record in invalid_records:
            issues.append(
                f"Reading ID {record.id} for Meter {record.meter_id} has future date {record.reading_date}"
            )

        return issues

    def check_price_rates_without_active_billing_range(self):
        """
        Check for PriceRate records where billing_range_active is NULL.
        """
        issues = []
        invalid_records = PriceRate.objects.filter(billing_range_active__isnull=True)

        for record in invalid_records:
            issues.append(
                f"PriceRate ID {record.id} ({record.token or record.name}) has no active BillingRange"
            )

        return issues

    def check_active_billing_ranges_without_line_items(self):
        """
        Check for active BillingRange records that have no associated LineItemTypes.
        """
        issues = []
        # Assuming 'line_item_types' is the related_name from LineItemType.billing_range
        invalid_records = BillingRange.objects.filter(
            is_active=True, line_item_types__isnull=True
        )

        for record in invalid_records:
            issues.append(
                f"BillingRange ID {record.id} ({record.name}) is active but has no LineItemTypes"
            )

        return issues

    def check_persons_duplicate_tokens(self):
        """
        Check for Person records with duplicate tokens.
        """
        issues = []
        duplicates = (
            Person.objects.values("token")
            .annotate(token_count=Count("token"))
            .filter(token_count__gt=1)
        )

        for entry in duplicates:
            token = entry["token"]
            count = entry["token_count"]
            issues.append(f"Person token '{token}' is duplicated {count} times")

        return issues

    def check_persons_forbidden_token(self):
        """
        Check for Person records with the forbidden token '99999999R'.
        """
        issues = []
        invalid_records = Person.objects.filter(token="99999999R")

        for record in invalid_records:
            issues.append(
                f"Person ID {record.id} ({record.name} {record.surname}) has forbidden token '99999999R'"
            )

        return issues

    def check_persons_without_contact_nor_address_nor_contract(self):
        """
        Persones sense contacte, ni adreça, ni cap contracte. Són registres zombi.
        """
        from watchdog.persons_without_contact import check_zombie_person_issues

        return check_zombie_person_issues()

    def check_persons_without_contact_nor_address_with_active_contract(self):
        """
        Persones sense contacte ni adreça que tenen un contracte actiu.
        Només és un avís: s'ha de sanejar a mà des del contracte.
        """
        from watchdog.persons_without_contact import check_active_contract_person_issues

        return check_active_contract_person_issues()

    def check_contract_request_type_exploitation(self):
        """
        Check for ContractRequestType records with exploitation_id = NULL.
        """
        issues = []
        invalid_records = ContractRequestType.objects.filter(exploitation__isnull=True)

        for record in invalid_records:
            issues.append(
                f"ContractRequestType ID {record.id} ({record.name}) has exploitation = NULL"
            )

        return issues

    def check_clusters_without_city(self):
        """
        Check for Cluster records where address_city is NULL.
        """
        issues = []
        invalid_records = Cluster.objects.filter(address_city__isnull=True)

        for record in invalid_records:
            issues.append(
                f"Cluster ID {record.id} ({record.token}) has address_city = NULL"
            )

        return issues

    def check_contracts_duplicate_tokens(self):
        """
        Check for Contract records with duplicate tokens.
        """
        issues = []
        duplicates = (
            Contract.objects.values("token")
            .annotate(token_count=Count("token"))
            .filter(token_count__gt=1)
        )

        for entry in duplicates:
            token = entry["token"]
            count = entry["token_count"]
            issues.append(f"Contract token '{token}' is duplicated {count} times")

        return issues

    def check_contracts_without_piggybanks(self):
        """
        Check for Contract records with duplicate tokens.
        """
        issues = []
        missing = (
            Contract.objects.filter(piggy_bank__isnull=True)
        )

        for entry in missing:
            issues.append(f"Contract ID {entry.id} ({entry.token}) has no PiggyBank")

        return issues
    
    def check_contracts_without_estimatedbag(self):
        """
        Check for Contract records with no EstimatedBag.
        """
        issues = []
        missing = (
            Contract.objects.filter(estimated_bags__isnull=True)
        )

        for entry in missing:
            issues.append(f"Contract ID {entry.id} ({entry.token}) has no EstimatedBag")

        return issues

    def check_contracts_without_holder(self):
        """
        Check for Contract records where holder is NULL.
        """
        issues = []
        invalid_records = Contract.objects.filter(holder__isnull=True)

        for record in invalid_records:
            issues.append(f"Contract ID {record.id} ({record.token}) has holder = NULL")

        return issues

    def check_exploitations_integrity(self):
        """
        Check for Exploitation records without cities OR without code.
        """
        issues = []
        # Check if cities is empty OR code is NULL OR code is empty string.
        invalid_records = (
            Exploitation.objects.filter(cities__isnull=True)
            | Exploitation.objects.filter(code__isnull=True)
            | Exploitation.objects.filter(code="")
        )

        invalid_records = invalid_records.distinct()

        for record in invalid_records:
            issues.append(
                f"Exploitation ID {record.id} ({record.name}) has no cities OR no code"
            )

        return issues

    def check_contracts_without_supply_points(self):
        """
        Check for Contract records that have no associated SupplyPoints.
        """
        issues = []
        invalid_records = Contract.objects.filter(supply_points__isnull=True)

        for record in invalid_records:
            issues.append(
                f"Contract ID {record.id} ({record.token}) has no SupplyPoints"
            )

        return issues

    def check_contracts_with_supply_points_no_meter(self):
        """
        Contractes actius amb algun punt de subministrament sense comptador.
        En un contracte de baixa és normal que el punt ja no tingui comptador:
        el tornen a posar quan facin l'alta.
        """
        try:
            active_token = ConfigProject.objects.get(token="contract_active_token").value
        except ConfigProject.DoesNotExist:
            return [
                "Error de configuració: no existeix ConfigProject «contract_active_token»"
            ]

        issues = []
        invalid_records = Contract.objects.filter(
            status__token=active_token,
            supply_points__meter__isnull=True,
        ).distinct()

        for record in invalid_records:
            issues.append(
                f"Contracte actiu ID {record.id} ({record.token}) té un punt de subministrament sense comptador"
            )

        return issues

    def check_supply_points_multiple_contracts(self):
        """
        Check for SupplyPoint records associated with more than one Contract.
        """
        try:
            config = ConfigProject.objects.get(token="contract_active_token")
            active_status_token = config.value
            active_status = ContractStatus.objects.get(token=active_status_token)
            active_status_id = active_status.id
        except (ConfigProject.DoesNotExist, ContractStatus.DoesNotExist):
            return [
                "Configuration error: 'contract_active_token' or corresponding ContractStatus not found."
            ]
        issues = []
        # Assuming 'contracts' is the related_name from Contract.supply_points
        invalid_records = SupplyPoint.objects.annotate(
            contract_count=Count("contracts")
        ).filter(contract_count__gt=1, status_id=active_status_id)

        for record in invalid_records:
            issues.append(
                f"SupplyPoint ID {record.id} ({record.token or record.name}) is associated with {record.contract_count} Contracts"
            )

        return issues

    def check_connections_multiple_supply_points_without_cluster(self):
        """
        Escomeses (Connection) amb més d'un SupplyPoint actiu i sense cap Cluster (bateria) vinculat.
        """
        issues = []

        cluster_exists = Cluster.objects.filter(
            connection=OuterRef("pk"),
            is_active=True,
        )

        invalid_connections = (
            Connection.objects.filter(is_active=True)
            .annotate(
                sp_active_count=Count(
                    "supply_points",
                    filter=Q(supply_points__is_active=True),
                    distinct=True,
                ),
                has_cluster=Exists(cluster_exists),
            )
            .filter(sp_active_count__gt=1, has_cluster=False)
            .order_by("id")
        )

        for conn in invalid_connections:
            token = conn.token or "sense token"
            issues.append(
                f"Connection ID {conn.id} ({token}) té {conn.sp_active_count} "
                f"SupplyPoints actius i cap Cluster (bateria) vinculat"
            )

        return issues

    def check_billing_ranges_without_price_rate(self):
        """
        Check for BillingRange records where price_rate is NULL.
        """
        issues = []
        invalid_records = BillingRange.objects.filter(price_rate__isnull=True)

        for record in invalid_records:
            issues.append(
                f"BillingRange ID {record.id} ({record.name}) has no PriceRate"
            )

        return issues

    def check_billing_ranges_without_publication(self):
        """
        Check for BillingRange records where publication is NULL.
        """
        issues = []
        invalid_records = BillingRange.objects.filter(publication__isnull=True)

        for record in invalid_records:
            issues.append(
                f"BillingRange ID {record.id} ({record.name}) has no Publication"
            )

        return issues

    def check_active_supply_points_sharing_cluster_nozzle(self):
        """
        Check for active SupplyPoints (status from config) that share the same ClusterNozzle.
        """
        issues = []

        try:
            config = ConfigProject.objects.get(
                token="supply_point_status_activate_token"
            )
            active_status_token = config.value
            active_status = SupplyPointStatus.objects.get(token=active_status_token)
        except (ConfigProject.DoesNotExist, SupplyPointStatus.DoesNotExist):
            return [
                "Configuration error: 'supply_point_status_activate_token' or corresponding SupplyPointStatus not found."
            ]

        # Find ClusterNozzles used by more than one active SupplyPoint
        duplicates = (
            SupplyPoint.objects.filter(
                status=active_status, cluster_nozzle__isnull=False
            )
            .values("cluster_nozzle")
            .annotate(sp_count=Count("id"))
            .filter(sp_count__gt=1)
        )

        for entry in duplicates:
            cluster_id = ClusterNozzle.objects.get(
                id=entry["cluster_nozzle"]
            ).cluster_id
            cluster_nozzle_id = entry["cluster_nozzle"]
            count = entry["sp_count"]
            issues.append(
                f"ClusterNozzle ID {cluster_nozzle_id} in Cluster ID {cluster_id} is shared by {count} active SupplyPoints"
            )

        return issues

    def check_meters_without_caliber(self):
        """
        Check for Meter records where caliber is NULL.
        """
        issues = []
        invalid_records = Meter.objects.filter(caliber__isnull=True)

        for record in invalid_records:
            issues.append(f"Meter ID {record.id} ({record.code}) has caliber = NULL")

        return issues

    def check_if_config_json_loaded_correctly(self):
        """
        Check if all ConfigProject entries from the JSON fixture are loaded correctly in the database.
        Compares token, name, and value fields.
        """
        from watchdog.config_project_fixture import (
            WATCHDOG_FIX_CONFIG_PROJECT_COMMAND,
            get_missing_config_project_entries,
            load_config_project_fixture_entries,
        )

        issues = []

        try:
            load_config_project_fixture_entries()
        except FileNotFoundError as exc:
            return [str(exc)]
        except ValueError as exc:
            return [str(exc)]

        for entry in get_missing_config_project_entries():
            issues.append(
                f"ConfigProject '{entry['token']}' ({entry['name']}) not found in database"
            )

        if issues:
            issues.append("")
            issues.append("Recomanació (watchdog): crea els ConfigProject que falten amb:")
            for line in WATCHDOG_FIX_CONFIG_PROJECT_COMMAND.splitlines():
                issues.append(f"  {line}")

        return issues

    def check_supply_points_with_meter_and_property_without_route_position(self):
        """
        Check for SupplyPoints that have a Meter and a Property, but the Property doesn't have a RoutePosition.
        """
        issues = []

        # Find SupplyPoints that have:
        # - meter (not null)
        # - property (not null)
        # - property.route_position is null
        invalid_supply_points = SupplyPoint.objects.filter(
            meter__isnull=False,
        ).filter(
            Q(property__isnull=True) | Q(property__route_position__isnull=True)
        ).select_related('meter', 'property')

        for supply_point in invalid_supply_points:
            meter_code = supply_point.meter.code if supply_point.meter else "N/A"
            supply_point_token = supply_point.token if supply_point.token else f"ID {supply_point.id}"
            issues.append(
                f"SupplyPoint {supply_point_token} té un Meter ({meter_code}) i una Property, "
                f"però la Property no té RoutePosition"
            )

        return issues
    
    def check_all_person_bank_and_company_bank_ibans(self):
        """
        Check PersonBank and CompanyBank for valid and not null iban
        """
        from coredata.utils.iban_validator_utils import validate_iban

        issues = []

        # Check PersonBank IBANs
        person_banks = PersonBank.objects.all()
        for pb in person_banks:
            if not pb.iban or not validate_iban(pb.iban):
                issues.append(
                    f"PersonBank ID {pb.id} for Person ID {pb.person_id} has invalid or null IBAN: '{pb.iban}'"
                )

        # Check CompanyBank IBANs
        company_banks = CompanyBank.objects.all()
        for cb in company_banks:
            if not cb.iban or not validate_iban(cb.iban):
                issues.append(
                    f"CompanyBank ID {cb.id} for Company ID {cb.company_id} has invalid or null IBAN: '{cb.iban}'"
                )

        return issues

    def check_all_confirmed_invoices_with_paid_payments(self):
        """
        Check for Confirmed Invoices that have Paid payments
        """
        issues = []
        
        confirmed_invoices = Invoice.objects.filter(status=InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_confirmed_token').value)).filter(payments__status=PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)).distinct()
        for invoice in confirmed_invoices:
            issues.append(
                f"Invoice ID {invoice.id} ({invoice.token}) has Paid payments"
            )
        return issues
    
    def check_contract_pricerate_supply_point_mismatch(self):
        """
        Contractes amb algun ContractPriceRate vinculat a contract.price_rates
        amb supply_point diferent dels contract.supply_points (o sense supply_point).
        Els CPR es poden compartir entre contractes; cal correcció per M2M + nous CPR.
        """
        contract_qs = (
            Contract.objects.filter(supply_points__isnull=False)
            .prefetch_related(
                "supply_points",
                Prefetch(
                    "price_rates",
                    queryset=ContractPriceRate.objects.select_related(
                        "supply_point", "price_rate"
                    ),
                )
            )
            .order_by("id")
        )

        issues = []
        affected_contract_ids = set()

        for contract in contract_qs.iterator(chunk_size=200):
            contract_supply_point_ids = set(
                contract.supply_points.values_list("id", flat=True)
            )
            token = contract.token or ""
            for cpr in contract.price_rates.all():
                if cpr.supply_point_id in contract_supply_point_ids:
                    continue
                affected_contract_ids.add(contract.id)
                other_n = cpr.contracts_price_rates.exclude(pk=contract.pk).count()
                shared = (
                    f"; CPR compartit amb {other_n} altre(s) contracte(s)"
                    if other_n
                    else ""
                )
                pr_part = (
                    f"price_rate_id={cpr.price_rate_id}"
                    if cpr.price_rate_id
                    else "sense price_rate"
                )
                issues.append(
                    f"Contract ID {contract.id} ({token}) té ContractPriceRate ID {cpr.id} amb "
                    f"supply_point_id={cpr.supply_point_id} que no pertany als supply_points del contracte "
                    f"({pr_part}){shared}"
                )

        if affected_contract_ids:
            ids_arg = ",".join(str(i) for i in sorted(affected_contract_ids))
            issues.append("")
            issues.append(
                "Recomanació (watchdog): corregeix aquestes anomalies amb el script "
                "fix_contract_pricerate_supply_point — primer simulació (--dry-run), després sense."
            )
            issues.append(
                f"  python manage.py fix_contract_pricerate_supply_point --dry-run --contract-ids \"{ids_arg}\""
            )
            issues.append(
                f"  python manage.py fix_contract_pricerate_supply_point --contract-ids \"{ids_arg}\""
            )

        return issues

    def check_main_company_token_matches_company_vat(self):
        """
        Comprova que ConfigProject 'main_company_token' apunta a un NIF existent (Company.vat).
        """
        issues = []
        try:
            config = ConfigProject.objects.get(token="main_company_token")
        except ConfigProject.DoesNotExist:
            return [
                "No existeix ConfigProject amb token 'main_company_token'."
            ]

        raw_value = config.value
        if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
            issues.append(
                "ConfigProject 'main_company_token' té el valor buit; ha de coincidir amb el NIF (Company.vat) d'alguna companyia."
            )
        else:
            value = raw_value.strip()
            if not Company.objects.filter(vat=value).exists():
                issues.append(
                    f"ConfigProject 'main_company_token' té valor '{value}' que no coincideix amb cap Company.vat."
                )

        if issues:
            issues.append("")
            issues.append(
                "Recomanació (watchdog): assigna el NIF de la primera Company (id ASC) amb:"
            )
            issues.append("  python manage.py watchdog_fix_main_company_token")

        return issues

    def check_default_country_province_city(self):
        """
        Comprova que Country, Province i City tenen almenys un registre amb is_default=True.
        """
        issues = []
        if not Country.objects.filter(is_default=True).exists():
            issues.append(
                "Coredata.Country: no hi ha cap registre amb is_default=True."
            )
        if not Province.objects.filter(is_default=True).exists():
            issues.append(
                "Coredata.Province: no hi ha cap registre amb is_default=True."
            )
        if not City.objects.filter(is_default=True).exists():
            issues.append(
                "Coredata.City: no hi ha cap registre amb is_default=True."
            )

        if issues:
            issues.append("")
            issues.append(
                "Recomanació (watchdog): assigna per defecte country, province i city "
                "segons l'adreça de la primera Company (id ASC) amb:"
            )
            issues.append("  python manage.py watchdog_fix_default_geo_from_company")

        return issues

    def check_postal_codes(self):
        issues = []
        # PostalCode: code is null OR length(code) < 5
        postal_codes = (
            PostalCode.objects
            .annotate(code_len=Length("code"))
            .filter(Q(code__isnull=True) | Q(code_len__lt=5))
            .distinct()
        )
        for pc in postal_codes:
            issues.append(
                f"PostalCode ID {pc.id} ({pc.code}) has no code or code is less than 5 characters: {pc.code}"
            )
        # Address: postal_code is null OR length(postal_code) < 5
        addresses = (
            Address.objects
            .annotate(pc_len=Length("postal_code"))
            .filter(Q(postal_code__isnull=True) | Q(pc_len__lt=5))
            .distinct()
        )
        for a in addresses:
            issues.append(
                f"Address ID {a.id} ({a.postal_code}) has no postal code or postal code is less than 5 characters: {a.postal_code}"
            )
        return issues

    def check_invoice_sequence_sync(self):
        """
        Comprova que InvoiceSequence.last_number no quedi per sota del màxim
        ja assignat a Invoice.serie_final per al mateix prefix (p. ex. FC/1826).
        Si queda desfasat, generate_serie_final intenta reutilitzar números i
        pot fallar amb IntegrityError de unique constraint.
        """
        issues = []
        desynced = find_desynced_invoice_sequences()
        for item in desynced:
            issues.append(
                f"InvoiceSequence '{item['prefix']}' té last_number={item['last_number']} "
                f"però ja existeix serie_final={item['max_serie_final']} "
                f"(màxim numèric={item['max_number']})"
            )
        if desynced:
            issues.append(
                "  python manage.py watchdog_fix_invoice_sequences --dry-run"
            )
            issues.append(
                "  python manage.py watchdog_fix_invoice_sequences"
            )
        return issues

    def check_invoices_without_company(self):
        """
        Check for Invoices without an assigned Company.
        """
        issues = []
        invalid_invoices = Invoice.objects.filter(is_active=True, company__isnull=True, serie_final__contains='/').order_by('id')
        for invoice in invalid_invoices:
            issues.append(
                f"Factura ID {invoice.id} ({invoice.token or invoice.number or 'Sense token'}) no té cap Empresa assignada"
            )
        return issues

    def check_invoices_without_exploitation(self):
        """
        Check for Invoices without an assigned Exploitation.
        """
        issues = []
        invalid_invoices = Invoice.objects.filter(is_active=True, exploitation__isnull=True, serie_final__contains='/').order_by('id')
        for invoice in invalid_invoices:
            issues.append(
                f"Factura ID {invoice.id} ({invoice.token or invoice.number or 'Sense token'}) no té cap Explotació assignada"
            )
        return issues

    def check_invoices_without_contract_or_person(self):
        """
        Detecta factures actives sense persona.
        Si té contracte, mostra el seu token; si també falta el contracte, ho indica.
        Exclou pressupostos (serie_final que comença per P).
        """
        issues = []
        invalid_invoices = (
            Invoice.objects.filter(
                is_active=True,
                serie_final__contains='/',
                person__isnull=True,
            )
            .exclude(serie_final__startswith='P')
            .select_related('contract', 'person')
            .order_by('id')
        )

        max_display = 50
        total = invalid_invoices.count()
        for invoice in invalid_invoices[:max_display]:
            missing = ['persona']
            related_parts = []

            if invoice.contract_id is None:
                missing.append('contracte')
            else:
                related_parts.append(
                    f"contracte token '{invoice.contract.token or 'Sense token'}'"
                )

            missing_label = ' i '.join(missing)
            serie = invoice.serie_final or invoice.token or invoice.number or 'Sense sèrie'
            message = (
                f"Factura ID {invoice.id} ({serie}) no està relacionada amb {missing_label}"
            )
            if related_parts:
                message += f" (sí relacionada amb {', '.join(related_parts)})"
            issues.append(message)

        if total > max_display:
            issues.append(
                f"... i {total - max_display} factures més sense persona "
                f"(total: {total})"
            )

        return issues

    def check_incidents_exist(self):
        """
        Informa si no hi ha cap Incident a la base de dades.
        """
        if Incident.objects.exists():
            return []
        return ["No hi ha cap incidència a la base de dades"]

    def check_payments_without_movements(self):
        """
        Detecta pagaments actius en estat Pagat, Retornat o En saldo (hucha)
        sense cap PaymentMovement actiu.
        """
        issues = []
        try:
            paid_token = ConfigProject.objects.get(token='payment_status_paid_token').value
            returned_token = ConfigProject.objects.get(token='payment_status_returned_token').value
            piggy_token = ConfigProject.objects.get(token='payment_status_piggy_token').value
        except ConfigProject.DoesNotExist as exc:
            return [f"Error de configuració: {exc}"]

        status_tokens = [paid_token, returned_token, piggy_token]
        has_active_movement = Exists(
            PaymentMovement.objects.filter(
                payment_id=OuterRef('pk'),
                is_active=True,
            )
        )

        payments = (
            Payment.objects.filter(
                is_active=True,
                status__token__in=status_tokens,
            )
            .annotate(_has_movement=has_active_movement)
            .filter(_has_movement=False)
            .select_related('status', 'invoice', 'contract')
            .order_by('id')
        )

        max_display = 50
        total = payments.count()
        for payment in payments[:max_display]:
            status_name = payment.status.name if payment.status else payment.status_id
            invoice_ref = (
                payment.invoice.serie_final
                or payment.invoice.token
                or payment.invoice_id
            ) if payment.invoice_id else 'Sense factura'
            issues.append(
                f"Pagament ID {payment.id} ({payment.token or 'Sense token'}) "
                f"en estat '{status_name}' sense moviments "
                f"(Factura {invoice_ref})"
            )

        if total > max_display:
            issues.append(
                f"... i {total - max_display} pagaments més sense moviments "
                f"(total: {total})"
            )

        return issues

    def check_payoff_invoices_missing_negative_balance_movement(self):
        """
        Si una factura d'abonament té una factura abonada amb pagament vinculat
        a un moviment de saldo positiu, l'abonament hauria de tenir un
        PaymentMovement negatiu al seu pagament.
        """
        issues = []
        try:
            payoff_status = InvoiceStatus.objects.get(
                token=ConfigProject.objects.get(token='invoice_status_payoff_token').value
            )
        except (ConfigProject.DoesNotExist, InvoiceStatus.DoesNotExist) as exc:
            return [f"Error de configuració: {exc}"]

        positive_piggy = Exists(
            PiggyBankMovement.objects.filter(
                payment__invoice_id=OuterRef('pk'),
                is_positive=True,
                is_active=True,
            )
        )
        positive_person_piggy = Exists(
            PersonPiggyBankMovement.objects.filter(
                payment__invoice_id=OuterRef('pk'),
                is_positive=True,
                is_active=True,
            )
        )
        negative_payment_movement = Exists(
            PaymentMovement.objects.filter(
                payment__invoice_id=OuterRef('pk'),
                is_positive=False,
                is_active=True,
            )
        )

        # Factures originals (abonades) amb moviment de saldo positiu
        original_invoices = (
            Invoice.objects.filter(
                is_active=True,
                return_token__isnull=False,
            )
            .exclude(return_token='')
            .annotate(
                _has_positive_balance=positive_piggy | positive_person_piggy,
            )
            .filter(_has_positive_balance=True)
            .only('id', 'token', 'serie_final', 'return_token')
        )

        payoff_by_token = {
            inv.token: inv
            for inv in Invoice.objects.filter(
                is_active=True,
                status=payoff_status,
                token__in=original_invoices.values_list('return_token', flat=True),
            )
            .annotate(
                _has_negative_payment_movement=negative_payment_movement,
            )
            .filter(_has_negative_payment_movement=False)
            .only('id', 'token', 'serie_final')
        }

        max_display = 50
        matched = []
        for original in original_invoices.iterator(chunk_size=200):
            payoff = payoff_by_token.get(original.return_token)
            if payoff:
                matched.append((original, payoff))

        total = len(matched)
        for original, payoff in matched[:max_display]:
            original_ref = original.serie_final or original.token or original.id
            payoff_ref = payoff.serie_final or payoff.token or payoff.id
            issues.append(
                f"Factura abonament ID {payoff.id} ({payoff_ref}) sense moviment de pagament "
                f"negatiu, però la factura abonada ID {original.id} ({original_ref}) "
                f"té pagament amb moviment de saldo positiu"
            )

        if total > max_display:
            issues.append(
                f"... i {total - max_display} abonaments més sense moviment de pagament "
                f"negatiu (total: {total})"
            )

        return issues

    def check_invoices_with_inconsistent_status(self):
        """
        Detecta factures en un estat no pagat (Vençuda, Confirmada, Enviada, etc.)
        que tenen tots els seus pagaments en estat Pagat.
        Indica una inconsistència: el pagament ja s'ha registrat però l'estat
        de la factura no s'ha actualitzat correctament.
        """
        issues = []

        try:
            paid_invoice_status = InvoiceStatus.objects.get(
                token=ConfigProject.objects.get(token='invoice_status_paid_token').value
            )
            cancelled_invoice_status = InvoiceStatus.objects.get(
                token=ConfigProject.objects.get(token='invoice_status_cancelled_token').value
            )
            payoff_invoice_status = InvoiceStatus.objects.get(
                token=ConfigProject.objects.get(token='invoice_status_payoff_token').value
            )
            paid_payment_status = PaymentStatus.objects.get(
                token=ConfigProject.objects.get(token='payment_status_paid_token').value
            )
        except (ConfigProject.DoesNotExist, InvoiceStatus.DoesNotExist, PaymentStatus.DoesNotExist) as e:
            return [f"Error de configuració: {e}"]

        from billing.models import Payment
        from django.db.models import Subquery

        # Factures que NO estan en estat pagat/cancel·lat/abonament i que tenen pagaments
        non_paid_invoices = Invoice.objects.exclude(
            status__in=[paid_invoice_status, cancelled_invoice_status, payoff_invoice_status]
        ).filter(payments__isnull=False).distinct()

        for invoice in non_paid_invoices:
            invoice_payments = Payment.objects.filter(invoice=invoice)
            if not invoice_payments.exists():
                continue
            all_paid = not invoice_payments.exclude(status=paid_payment_status).exists()
            if all_paid:
                contract_id = invoice.contract_id or 'N/A'
                issues.append(
                    f"Factura ID {invoice.id} ({invoice.token or invoice.number or 'Sense token'}) "
                    f"en estat '{invoice.status}' però tots els seus pagaments estan Pagats "
                    f"(Contracte ID {contract_id})"
                )

        if issues:
            issues.append("")
            issues.append(
                "Recomanació (watchdog): corregeix l'estat d'aquestes factures amb:"
            )
            issues.append(
                "  python manage.py watchdog_fix_invoice_status_from_payments --dry-run"
            )
            issues.append(
                "  python manage.py watchdog_fix_invoice_status_from_payments"
            )

        return issues

    def check_invoices_without_active_payment(self):
        """
        Detecta factures sense cap pagament actiu (excepte pre-factura).
        Aquestes factures queden excloses d'informes que filtren per payments__is_active=True.
        """
        issues = []

        try:
            invoice_type = ConfigProject.objects.get(
                token='invoice_type_invoice_token'
            ).value
        except ConfigProject.DoesNotExist as exc:
            return [f"Error de configuració: {exc}"]

        from billing.utils.confirm_invoice_service import build_invoices_without_active_payment_queryset

        queryset = build_invoices_without_active_payment_queryset().filter(
            type_final=invoice_type,
            serie_final__contains='/',
        )

        total = queryset.count()
        if total == 0:
            return issues

        max_display = 50
        for invoice in queryset[:max_display]:
            billing_part = (
                f", Billing ID {invoice.billing_id}" if invoice.billing_id else ""
            )
            issues.append(
                f"Factura ID {invoice.id} ({invoice.serie_final or invoice.token}) "
                f"sense pagament actiu{billing_part}"
            )

        if total > max_display:
            issues.append(
                f"... i {total - max_display} factures més sense pagament actiu "
                f"(total: {total})"
            )

        issues.append("")
        issues.append("Recomanació (watchdog): crea els pagaments que falten amb:")
        issues.append("  python manage.py create_payments_from_invoices --dry-run")
        issues.append("  python manage.py create_payments_from_invoices")
        issues.append("  (afegeix --billing-id N per limitar a un billing concret)")

        return issues

    def check_orphaned_addresses(self):
        """
        Identify Address records that are not linked to any Person, SupplyPoint, Order or Company.
        """
        from watchdog.orphaned_addresses import (
            WATCHDOG_FIX_ORPHANED_ADDRESSES_COMMAND,
            format_orphaned_address_issue,
            get_orphaned_addresses_queryset,
        )

        issues = []
        orphans = get_orphaned_addresses_queryset()
        total = orphans.count()

        if total == 0:
            return issues

        issues.append(
            f"S'han trobat {total} adreces orfes (sense relació amb Person, SupplyPoint, Order ni Company)"
        )

        max_display = 50
        for address in orphans[:max_display]:
            issues.append(format_orphaned_address_issue(address))

        if total > max_display:
            issues.append(
                f"... i {total - max_display} adreces orfes més (total: {total})"
            )

        issues.append("")
        issues.append("Recomanació (watchdog): elimina les adreces orfes amb:")
        for line in WATCHDOG_FIX_ORPHANED_ADDRESSES_COMMAND.splitlines():
            issues.append(f"  {line}")

        return issues

    def check_condition_variable_types(self):
        """Comprova que els condicionals amb referències variable.* tinguin VariableType vàlid."""
        return check_condition_variable_type_references()

    def check_aca_configuration(self):
        """Comprova configuració ACA (ConfigProject, VariableType i use_aca als contractes)."""
        return check_aca_configuration_issues()

    def check_aca_article_codes(self):
        """Comprova ArticleCode, LineItemType i contract_keeper_use_type_token per als informes ACA."""
        return check_aca_article_code_issues()

    def run_all_checks(self):
        """
        Run all integrity checks and return a dictionary of results.
        """
        results = {}

        # Check ContractRequestType exploitation
        results["ContractRequestType Exploitation"] = (
            self.check_contract_request_type_exploitation()
        )

        # Check Clusters without city
        results["Clusters without City"] = self.check_clusters_without_city()

        # Check Contracts duplicate tokens
        results["Contracts Duplicate Tokens"] = self.check_contracts_duplicate_tokens()
        
        # Check Contracts without piggybanks
        results["Contracts without Piggybanks"] = self.check_contracts_without_piggybanks()
        # Check Contracts without estimatedbags
        results["Contracts without EstimatedBag"] = self.check_contracts_without_estimatedbag()

        # Check Contracts without holder
        results["Contracts without Holder"] = self.check_contracts_without_holder()

        # Check Exploitations integrity
        results["Exploitations Integrity"] = self.check_exploitations_integrity()

        # Check Contracts without SupplyPoints
        results["Contracts without SupplyPoints"] = (
            self.check_contracts_without_supply_points()
        )

        # Contractes actius amb punts de subministrament sense comptador
        results["Contractes actius amb SupplyPoints sense Meter"] = (
            self.check_contracts_with_supply_points_no_meter()
        )

        # Check SupplyPoints with multiple Contracts
        results["SupplyPoints Multiple Contracts"] = (
            self.check_supply_points_multiple_contracts()
        )

        # Escomeses amb múltiples PS actius sense bateria (Cluster) vinculada
        results["Escomeses amb múltiples PS sense Bateria"] = ( self.check_connections_multiple_supply_points_without_cluster())

        # Check Persons duplicate tokens
        results["Persons Duplicate Tokens"] = self.check_persons_duplicate_tokens()

        results[ZOMBIE_PERSONS_CHECK_NAME] = (
            self.check_persons_without_contact_nor_address_nor_contract()
        )
        results[ACTIVE_CONTRACT_CHECK_NAME] = (
            self.check_persons_without_contact_nor_address_with_active_contract()
        )

        # Check Persons forbidden token
        # results['Persons Forbidden Token'] = self.check_persons_forbidden_token()

        # Check PriceRates without active BillingRange
        results["PriceRates without Active BillingRange"] = (
            self.check_rates_without_active_billing_range() if hasattr(self, 'check_rates_without_active_billing_range') else self.check_price_rates_without_active_billing_range()
        )

        # Check active BillingRanges without LineItemTypes
        # results['Active BillingRanges without LineItemTypes'] = self.check_active_billing_ranges_without_line_items()

        # Check BillingRanges without PriceRate
        results["BillingRanges without PriceRate"] = (
            self.check_billing_ranges_without_price_rate()
        )

        # Check BillingRanges without Publication
        results["BillingRanges without Publication"] = (
            self.check_billing_ranges_without_publication()
        )

        # Check active SupplyPoints sharing ClusterNozzle
        results["Active SupplyPoints sharing ClusterNozzle"] = (
            self.check_active_supply_points_sharing_cluster_nozzle()
        )

        # Check future Readings
        results["Lectures amb Data Futura"] = self.check_future_readings()

        # Readings without meter_id
        results["Lectures sense Comptador (meter_id)"] = (
            self.check_readings_without_meter()
        )

        # Active contracts: last Reading meter must belong to a contract SupplyPoint
        results["Contractes Actius: última Lectura amb Meter no vinculat"] = (
            self.check_active_contracts_last_reading_meter_mismatch()
        )

        # Check Digital Contracts without email
        results["Contractes Digitals sense Correu"] = (
            self.check_digital_contracts_without_email()
        )

        # Check Meters duplicate tokens
        results["Comptadors amb Tokens Duplicats"] = (
            self.check_meters_duplicate_tokens()
        )

        # Check Active Contracts sharing Meter
        results["Contractes Actius compartint Comptador"] = (
            self.check_active_contracts_sharing_meter()
        )

        # Contractes actius sense cap PriceRate (via ContractPriceRate)
        results["Contractes Actius sense PriceRate"] = (
            self.check_active_contracts_without_price_rate()
        )

        # Check Meters without caliber
        results["Comptadors sense Calibre"] = self.check_meters_without_caliber()

        # Check if ConfigProject JSON is loaded correctly
        results["ConfigProject JSON carregat correctament"] = (
            self.check_if_config_json_loaded_correctly()
        )

        # main_company_token ha de ser un Company.vat vàlid
        results["main_company_token vs Company.vat"] = (
            self.check_main_company_token_matches_company_vat()
        )

        # Country, Province i City amb is_default
        results["Country, Province i City per defecte"] = (
            self.check_default_country_province_city()
        )

        # Check SupplyPoints with Meter and Property without RoutePosition
        results["SupplyPoints amb Meter i Property sense RoutePosition"] = (
            self.check_supply_points_with_meter_and_property_without_route_position()
        )
        
        # Check all PersonBank and CompanyBank IBANs
        results["PersonBank i CompanyBank IBANs vàlids"] = (
            self.check_all_person_bank_and_company_bank_ibans()
        )
        
        # Check all Confirmed Invoices that have Paid payments
        results["Invoices Confirmed amb Payments Pagats"] = (
            self.check_all_confirmed_invoices_with_paid_payments()
        )
        
        # Postal codes with incorrect format
        results["Codi postal i Address (format)"] = self.check_postal_codes()

        # Contract M2M price_rates: ContractPriceRate.supply_point vs supply_point_default
        results["ContractPriceRate vs supply_point_default"] = (
            self.check_contract_pricerate_supply_point_mismatch()
        )

        # Orphaned Addresses
        results["Adreces Orfes"] = self.check_orphaned_addresses()

        # InvoiceSequence.last_number vs max serie_final
        results["InvoiceSequence desfasada (serie_final)"] = (
            self.check_invoice_sequence_sync()
        )

        # Invoices without Company
        results["Factures sense Empresa"] = self.check_invoices_without_company()

        # Invoices without Exploitation
        results["Factures sense Explotació"] = self.check_invoices_without_exploitation()

        # Invoices without Contract and/or Person
        results["Factures sense Contracte o Persona"] = (
            self.check_invoices_without_contract_or_person()
        )

        # Incidents: avisa si no n'hi ha cap a la BD
        results["Incidències a la BD"] = self.check_incidents_exist()

        # Payments in paid/returned/piggy without PaymentMovement
        results["Pagaments sense Moviments"] = self.check_payments_without_movements()

        # Payoff invoices missing negative PaymentMovement when original has positive saldo
        results["Abonaments sense Moviment de Pagament Negatiu"] = (
            self.check_payoff_invoices_missing_negative_balance_movement()
        )

        # Invoices with inconsistent status (non-paid invoice but all payments are paid)
        results["Factures amb Estat Inconsistent (Pagaments Pagats)"] = (
            self.check_invoices_with_inconsistent_status()
        )

        # Confirmed/payoff invoices missing an active payment
        results["Factures sense Pagament Actiu"] = (
            self.check_invoices_without_active_payment()
        )

        # Condicionals amb referències a VariableType inexistents
        results["Condicionals amb referències VariableType"] = (
            self.check_condition_variable_types()
        )

        # ACA configuration and contract use_aca
        results["Configuració ACA i use_aca"] = self.check_aca_configuration()

        results["ArticleCode per informes ACA"] = self.check_aca_article_codes()

        return results

