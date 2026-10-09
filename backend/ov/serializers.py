from rest_framework import serializers
from contract.models import (
    Contract,
    ContractDataChange,
    ContractLog,
    ContractObservation,
    ContractTerminationRequest,
    PaymentType,
)
from billing.models import (
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
    Payment,
    PaymentStatus,
    Reading,
)
from billing.utils.payment_service import get_status_map
from decouple import config
from coredata.models import ConfigProject, Person, PersonAddress, PersonBank, PersonContact, Country
from django.utils import timezone
from django.db import transaction
from django.utils.dateparse import parse_date


class ContractSerializer(serializers.ModelSerializer):
    status_token = serializers.CharField(source="status.token", read_only=True)
    status_name = serializers.CharField(source="status.name", read_only=True)
    holder_token = serializers.CharField(source="holder.token", read_only=True)
    payment_type = serializers.CharField(source="payment.type.token", read_only=True)
    use_type = serializers.CharField(source="use_type.name", read_only=True)
    last_invoice_date = serializers.SerializerMethodField()
    iban = serializers.SerializerMethodField()
    supply_point_address = serializers.SerializerMethodField()
    meter_serial_number = serializers.CharField(
        source="supply_point_default.meter.token", read_only=True
    )
    meter_caliber = serializers.CharField(
        source="supply_point_default.meter.caliber.name", read_only=True
    )
    smart_metering = serializers.SerializerMethodField()
    
    registration_date = serializers.SerializerMethodField()
    termination_date = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = [
            "token",
            "status_token",
            "status_name",
            "holder_token",
            "payment_type",
            "use_type",
            "last_invoice_date",
            "iban",
            "supply_point_address",
            "meter_serial_number",
            "meter_caliber",
            "smart_metering",
            "registration_date",
            "termination_date",
        ]
    
    def get_registration_date(self, obj):
        if obj.registration_date:
            return obj.registration_date.strftime("%d/%m/%Y")
        return obj.created_at.strftime("%d/%m/%Y")
    
    def get_termination_date(self, obj):
        contract_termination_completed_token = ConfigProject.objects.get(token="contract_termination_completed_token").value
        contract_terminated_status = ConfigProject.objects.get(token="contract_terminated_status").value
        termination = ContractTerminationRequest.objects.filter(
            contract=obj,
            status__token=contract_termination_completed_token
        ).first()
        if termination and obj.status.token == contract_terminated_status:
            return termination.approved_at.strftime("%d/%m/%Y") if termination.approved_at else termination.created_at.strftime("%d/%m/%Y")
        return None

    def get_last_invoice_date(self, obj):
        last_invoice = obj.invoices.order_by("-created_at").first()
        if last_invoice:
            return last_invoice.created_at
        return None

    def get_supply_point_address(self, obj):
        supply_point = obj.supply_point_default
        if supply_point:
            return str(supply_point.address)
        return None

    def get_smart_metering(self, obj):
        return "true" if obj.supply_point_default.meter.has_remote_reading else "false"

    def get_iban(self, obj):
        iban = obj.payment.IBAN.iban if obj.payment and obj.payment.IBAN else None
        if iban:
            first_part = iban[:8]
            last_part = iban[-8:]
            masked_middle = "*" * (len(iban) - 16)
            return f"{first_part}{masked_middle}{last_part}"
        return ""


class BillingDataOVSerializer(serializers.ModelSerializer):
    nif = serializers.CharField(source="holder.token", read_only=True)
    tenant_name = serializers.SerializerMethodField()
    supply_point_address = serializers.SerializerMethodField()
    city = serializers.CharField(
        source="supply_point_default.address.city.name", read_only=True
    )
    postal_code = serializers.CharField(
        source="supply_point_default.address.postal_code", read_only=True
    )
    paper_invoice = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    invoice_language = serializers.SerializerMethodField()
    phone1 = serializers.SerializerMethodField()
    phone2 = serializers.SerializerMethodField()
    payment_type = serializers.CharField(source="payment.type.token", read_only=True)
    iban = serializers.SerializerMethodField()
    holder_name = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = [
            "nif",
            "tenant_name",
            "supply_point_address",
            "city",
            "postal_code",
            "paper_invoice",
            "email",
            "invoice_language",
            "phone1",
            "phone2",
            "payment_type",
            "iban",
            "holder_name",
        ]

    def get_tenant_name(self, obj):
        return f"{obj.holder.name} {obj.holder.surname}"

    def get_holder_name(self, obj):
        return f"{obj.holder.name} {obj.holder.surname}"

    def get_supply_point_address(self, obj):
        supply_point = obj.supply_point_default
        if supply_point:
            return str(supply_point.address)
        return None

    def get_email(self, obj):
        contact = obj.person_contact_email
        if contact:
            return contact.email
        return ""

    def get_phone1(self, obj):
        contact = (
            obj.contacts.filter(is_default=True)
            .exclude(phone__isnull=True)
            .exclude(phone__exact="")
            .first()
        )
        if not contact:
            contact = (
                obj.contacts.exclude(phone__isnull=True)
                .exclude(phone__exact="")
                .first()
            )
        return contact.phone if contact else ""

    def get_phone2(self, obj):
        contact = (
            obj.contacts.filter(is_default=False)
            .exclude(phone__isnull=True)
            .exclude(phone__exact="")
            .first()
        )
        if not contact:
            contact = (
                obj.contacts.exclude(phone__isnull=True).exclude(phone__exact="").last()
            )
        return contact.phone if contact else ""

    def get_paper_invoice(self, obj):
        communication_type = obj.communication_type
        return "true" if communication_type != "DIGITAL" else "false"

    def get_invoice_language(self, obj):
        return config("INVOICE_LANGUAGE", default="en")

    def get_iban(self, obj):
        iban = obj.payment.IBAN.iban if obj.payment and obj.payment.IBAN else None
        if iban:
            first_part = iban[:8]
            last_part = iban[-8:]
            masked_middle = "*" * (len(iban) - 16)
            return f"{first_part}{masked_middle}{last_part}"
        return ""


class UpdateBillingDataOVSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone1 = serializers.CharField(required=False, allow_blank=True)
    phone2 = serializers.CharField(required=False, allow_blank=True)
    paper_invoice = serializers.BooleanField(required=True)

    def validate(self, data):
        """Validate input data"""
        if not data.get("paper_invoice") in [True, False]:
            raise serializers.ValidationError({"error": "paper invoice is required."})

        # Validate that phone1 and phone2 are different if both provided
        phone1 = data.get("phone1", "").strip()
        phone2 = data.get("phone2", "").strip()

        return data

    def _get_or_create_contact(self, holder, email=None, phone=None, is_default=True):
        filters = {"person": holder}
        if email:
            filters["email"] = email
        if phone:
            filters["phone"] = phone

        # Try to find existing contact
        existing_contact = PersonContact.objects.filter(**filters).first()

        if existing_contact:
            # Update existing contact
            existing_contact.is_default = is_default
            existing_contact.is_active = True
            existing_contact.save()
            return existing_contact, False
        else:
            # Create new contact
            contact = PersonContact.objects.create(
                person=holder,
                email=email,
                phone=phone,
                is_default=is_default,
                is_active=True,
                token=f"{holder.token}_CONTACT_{PersonContact.objects.filter(person=holder).count() + 1}",
            )
            return contact, True

    def update(self, instance: Contract, validated_data):

        try:
            holder = instance.holder
            if not holder:
                raise serializers.ValidationError({"error": "Contract has no holder"})

            with transaction.atomic():
                # Only update email if provided
                if email := validated_data.get("email"):
                    current_person_contact: PersonContact = (
                        instance.person_contact_email
                    )

                    email_contact, email_created = self._get_or_create_contact(
                        holder=holder, email=email, is_default=True
                    )

                    instance.person_contact_email = email_contact
                    instance.save()

                    if email_created and current_person_contact:
                        if instance.contacts.filter(
                            id=current_person_contact.id
                        ).exists():
                            instance.contacts.remove(current_person_contact)

                    if not instance.contacts.filter(id=email_contact.id).exists():
                        instance.contacts.add(email_contact)

                    # Log email change
                    ContractDataChange.objects.create(
                        token=f"CDC_{instance.token}_{ContractDataChange.objects.filter(contract=instance).count() + 1}",
                        requested_at=timezone.now(),
                        approved_at=timezone.now(),
                        contract=instance,
                        previous_person_contact_email=current_person_contact,
                        new_person_contact_email=email_contact,
                    )
                    ContractLog.objects.create(
                        contract=instance,
                        field_name="person_contact_email",
                        old_value=(
                            current_person_contact.email
                            if current_person_contact
                            else "None"
                        ),
                        new_value=email_contact.email,
                        operation_token=f"LOG_{instance.token}_{ContractLog.objects.filter(contract=instance).count() + 1}",
                        user=(
                            self.context["request"].user
                            if self.context.get("request")
                            else None
                        ),
                    )

                phone_1_contact = None
                if phone1 := validated_data.get("phone1"):
                    phone_1_contact, phone1_created = self._get_or_create_contact(
                        holder=holder, phone=phone1, is_default=True
                    )

                    PersonContact.objects.filter(person=holder).filter(
                        phone__isnull=False
                    ).exclude(id=phone_1_contact.id).update(is_default=False)

                    existing_default = (
                        instance.contacts.filter(is_default=True)
                        .exclude(id=phone_1_contact.id)
                        .filter(phone__isnull=False)
                        .first()
                    )
                    if (
                        existing_default
                        and instance.contacts.filter(id=existing_default.id).exists()
                    ):
                        instance.contacts.remove(existing_default)

                    if not instance.contacts.filter(id=phone_1_contact.id).exists():
                        instance.contacts.add(phone_1_contact)

                if phone2 := validated_data.get("phone2"):
                    phone_2_contact, phone2_created = self._get_or_create_contact(
                        holder=holder, phone=phone2, is_default=False
                    )

                    existing_non_defaults: list = (
                        instance.contacts.filter(is_default=False)
                        .exclude(id=phone_2_contact.id)
                        .filter(phone__isnull=False)
                    )

                    if existing_non_defaults:
                        # Remove all existing non-default phone contacts from the contract (if any)
                        for contact in existing_non_defaults:
                            if instance.contacts.filter(id=contact.id).exists():
                                instance.contacts.remove(contact)

                    if not instance.contacts.filter(id=phone_2_contact.id).exists():
                        instance.contacts.add(phone_2_contact)

                    if phone_1_contact:
                        PersonContact.objects.filter(
                            person=holder, phone__isnull=False
                        ).exclude(id=phone_1_contact.id).update(is_default=False)

                # Log observation only if there are changes
                observation_parts = []
                if validated_data.get("email"):
                    observation_parts.append(f"email = {validated_data.get('email')}")
                if validated_data.get("phone1"):
                    observation_parts.append(f"phone1 = {validated_data.get('phone1')}")
                if validated_data.get("phone2"):
                    observation_parts.append(f"phone2 = {validated_data.get('phone2')}")

                if observation_parts:
                    observation_text = "Added by Oficina Virtual:\n " + "\n ".join(
                        observation_parts
                    )

                    ContractObservation.objects.create(
                        user=(
                            self.context["request"].user
                            if self.context.get("request")
                            else None
                        ),
                        contract=instance,
                        observation=observation_text,
                    )

                current_communication_type = instance.communication_type
                new_communication_type = (
                    "PAPER" if validated_data["paper_invoice"] else "DIGITAL"
                )
                instance.communication_type = new_communication_type
                instance.save()

                # log communication_type change
                ContractLog.objects.create(
                    contract=instance,
                    field_name="communication_type",
                    old_value=current_communication_type,
                    new_value=new_communication_type,
                    operation_token=f"LOG_{instance.token}_{ContractLog.objects.filter(contract=instance).count() + 1}",
                    user=(
                        self.context["request"].user
                        if self.context.get("request")
                        else None
                    ),
                )

            return instance

        except Exception as e:
            raise serializers.ValidationError(
                {"error": f"Failed to update billing data: {str(e)}"}
            )


class UpdateBillingDataOVIBANSerializer(serializers.Serializer):
    iban = serializers.CharField(required=True)
    nif = serializers.CharField(required=True)
    iban_holder_name = serializers.CharField(required=True)
    iban_holder_dni = serializers.CharField(required=True)

    def validate(self, data):
        """Validate input data"""
        if not data.get("iban"):
            raise serializers.ValidationError({"iban": "IBAN is required."})
        if not data.get("nif"):
            raise serializers.ValidationError({"nif": "NIF is required."})
        if not data.get("iban_holder_name"):
            raise serializers.ValidationError(
                {"iban_holder_name": "IBAN holder name is required."}
            )
        if not data.get("iban_holder_dni"):
            raise serializers.ValidationError(
                {"iban_holder_dni": "IBAN holder DNI is required."}
            )

        # Clean IBAN format
        data["iban"] = data["iban"].replace(" ", "").upper()

        # Clean NIF format
        data["nif"] = data["nif"].strip().upper()
        data["iban_holder_dni"] = data["iban_holder_dni"].strip().upper()
        return data

    def update(self, instance: Contract, validated_data):
        try:
            holder: Person = instance.holder
            if not holder:
                raise serializers.ValidationError({"error": "Contract has no holder"})

            # Validate NIF matches contract holder
            if holder.token != validated_data["nif"]:
                raise serializers.ValidationError(
                    {"error": "NIF does not match the contract holder's NIF"}
                )

            if not instance.payment:
                raise serializers.ValidationError(
                    {"error": "Contract has no payment method to update IBAN"}
                )
            with transaction.atomic():
                person_bank_current = instance.payment.IBAN
                if person_bank_current:
                    person_bank_current.is_active = False
                    person_bank_current.is_default = False
                    person_bank_current.deactivated_at = timezone.now()
                    person_bank_current.save()

                person_bank_new = PersonBank.objects.create(
                    person=holder,
                    iban=validated_data["iban"],
                    account_number=validated_data["iban"],
                    name=validated_data["iban_holder_name"],
                    dni=validated_data["iban_holder_dni"],
                    is_active=True,
                    is_default=True,
                    country=Country.objects.filter(
                        iso_code=validated_data["iban"][:2]
                    ).first(),
                    token=f"{holder.token}_BANK_{PersonBank.objects.filter(person=holder).count() + 1}",
                )
                instance.payment.IBAN = person_bank_new
                instance.payment.save()
                instance.save()

                # Log the change in ContractDataChange
                ContractDataChange.objects.create(
                    token=f"CDC_{instance.token}_{ContractDataChange.objects.filter(contract=instance).count() + 1}",
                    requested_at=timezone.now(),
                    approved_at=timezone.now(),
                    contract=instance,
                    new_payment=person_bank_new,
                    previous_payment=person_bank_current,
                    user=(
                        self.context["request"].user
                        if self.context.get("request")
                        else None
                    ),
                )
                ContractLog.objects.create(
                    contract=instance,
                    field_name="payment_IBAN",
                    old_value=(
                        person_bank_current.iban if person_bank_current else "None"
                    ),
                    new_value=person_bank_new.iban,
                    operation_token=f"LOG_{instance.token}_{ContractLog.objects.filter(contract=instance).count() + 1}",
                    user=(
                        self.context["request"].user
                        if self.context.get("request")
                        else None
                    ),
                )

            return instance

        except Exception as e:
            raise serializers.ValidationError(
                {"error": f"Failed to update IBAN data: {str(e)}"}
            )


class BillingContractInvoicesOVSerializer(serializers.Serializer):

    contract_number = serializers.CharField(source="contract.token", read_only=True)
    invoice_number = serializers.CharField(source="serie_final", read_only=True)
    invoice_token = serializers.CharField(source="token", read_only=True)
    invoice_date = serializers.DateField(source="issue_date", read_only=True)
    invoice_amount = serializers.FloatField(source="left_to_pay", read_only=True)
    # only using invoice_amount in ov, no need for total_final (currently)
    # invoice_left_to_pay = serializers.FloatField(source="left_to_pay", read_only=True)

    invoice_status = serializers.CharField(source="status.name", read_only=True)
    pdf_available = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "contract_number",
            "invoice_number",
            "invoice_date",
            "invoice_amount",
            "invoice_status",
            "invoice_token",
            "pdf_available",
        ]

    def get_pdf_available(self, obj) -> bool:
        from coredata.models import ConfigProject

        date_str = ConfigProject.objects.filter(token="ov_pdf_from").first()
        if not date_str or not date_str.value:
            return True  # If config not set, assume all PDFs are available
        else:
            value = date_str.value
            pdf_from_date = parse_date(value)
            if obj.issue_date < pdf_from_date:
                return False
            return True


class InvoiceConsumptionSerializer(serializers.ModelSerializer):
    meter = serializers.CharField(source="contract.supply_point_default.meter.token")
    reading = serializers.SerializerMethodField()
    is_estimated = serializers.SerializerMethodField()
    origin = serializers.CharField(default="")
    contract_number = serializers.CharField(source="contract.token")

    class Meta:
        model = Invoice
        fields = [
            "meter",
            "reading",
            "consumption",
            "origin",
            "contract_number",
            "is_estimated",
        ]

    def get_reading(self, obj):
        # Get the latest reading for this invoice, or '' if none exist
        reading = obj.readings.order_by("-reading_date").first()
        return reading.reading_value if reading else ""

    def get_is_estimated(self, obj):
        reading = obj.readings.order_by("-reading_date").first()
        return reading.is_estimated if reading else False


class BilledConsumptionsOVSerializer(serializers.Serializer):
    timestamp = serializers.DateField(source="issue_date")
    consumptions = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = ["timestamp", "consumptions"]

    def get_consumptions(self, obj):
        # For each invoice, return its consumption data
        serializer = InvoiceConsumptionSerializer(obj)
        return [serializer.data]


class InvoicePaidSerializer(serializers.Serializer):
    contract_token = serializers.CharField(required=True)
    invoice_token = serializers.CharField(required=True)

    def validate(self, data):
        contract_token = data.get("contract_token")
        invoice_token = data.get("invoice_token")

        if not contract_token:
            raise serializers.ValidationError(
                {"contract_token": "Contract token is required."}
            )
        if not invoice_token:
            raise serializers.ValidationError(
                {"invoice_token": "Invoice token is required."}
            )

        return data

    def update(self, validated_data):
        print(validated_data)
        print(validated_data["invoice_token"])
        print(validated_data["contract_token"])
        print("--------------------------------")
        #invoice type invoice to avoid getting budgets
        invoice_type_invoice_token = ConfigProject.objects.get(token="invoice_type_invoice_token").value
        invoice: Invoice = Invoice.objects.filter(
            token=validated_data["invoice_token"],
            contract__token=validated_data["contract_token"],
            type_final=invoice_type_invoice_token
        ).first()
        print(invoice)
        print("--------------------------------")
        if not invoice:
            raise serializers.ValidationError(
                {"error": "Invoice not found for the given contract."}
            )

        try:
            payment_status_map = get_status_map()
            paid_status = payment_status_map["payment_status_paid_token"]
            
            #TODO: Review payment type assignment Hardcoded for TPV_ONLINE
            payment_type_by_token = PaymentType.objects.filter(token="TPV_ONLINE").first()
            
            
            payments = Payment.objects.filter(invoice=invoice)
            if not payments.exists():
                raise serializers.ValidationError(
                    {"error": "No payments found for this invoice."}
                )

            for payment in payments:
                # Skip payments that are already paid
                if payment.status == paid_status:
                    continue
                payment.status = paid_status
                payment.payment_type = "TPV ONLINE"
                
                if payment_type_by_token:
                    payment.payment_type_token = payment_type_by_token.token
                    
                payment.payment_date = timezone.now().date()
                payment.save()

            invoice.refresh_from_db()

            return invoice

        except Exception as e:
            raise serializers.ValidationError(
                {"error": f"Failed to mark invoice as paid: {str(e)}"}
            )


class InvoicePDFSerializer(serializers.ModelSerializer):
    contract_number = serializers.CharField(source="contract.token", read_only=True)
    status_name = serializers.CharField(source="status.name", read_only=True)
    customer_full_address = serializers.SerializerMethodField()
    issue_date_formatted = serializers.SerializerMethodField()
    due_date_formatted = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "token",
            "number",
            "contract_number",
            "issue_date_formatted",
            "due_date_formatted",
            "status_name",
            "customer_final",
            "customer_full_address",
            "customer_email_final",
            "customer_tlf_final",
            "subtotal_final",
            "total_final",
            "left_to_pay",
            "payment_iban_final",
            "title_final",
            "serie_final",
            "type_final",
        ]

    def get_customer_full_address(self, obj):
        address_parts = [
            obj.address_final,
            obj.postal_code_final,
            obj.city_final,
            obj.province_final,
            obj.country_final,
        ]
        return ", ".join(filter(None, address_parts))

    def get_issue_date_formatted(self, obj):
        return obj.issue_date.strftime("%d/%m/%Y") if obj.issue_date else ""

    def get_due_date_formatted(self, obj):
        return obj.due_date.strftime("%d/%m/%Y") if obj.due_date else ""


def mask_iban(iban):
    """
    Mask an IBAN keeping only the first and last 8 characters, following the
    convention documented for the OV API (8 primeros + asteriscos + 8 últimos).

    Returns "" for a missing value so the field always serialises as a string.
    Values of 16 characters or fewer are masked entirely: there is no room to
    keep both ends without disclosing the whole account.
    """
    if not iban:
        return ""
    iban = str(iban)
    if len(iban) <= 16:
        return "*" * len(iban)
    return f"{iban[:8]}{'*' * (len(iban) - 16)}{iban[-8:]}"


class ContractHolderOVSerializer(serializers.Serializer):
    """
    `contract_holder` — the contract holder (``Contract.holder``, a
    ``coredata.Person``).
    """

    dni = serializers.SerializerMethodField()
    nombre = serializers.SerializerMethodField()

    def get_dni(self, obj):
        return obj.token

    def get_nombre(self, obj):
        parts = [part for part in (obj.name, obj.surname) if part]
        return " ".join(parts) if parts else None


class ContractDebitHolderOVSerializer(serializers.Serializer):
    """
    `direct_debit_holder` — the holder of the direct-debit account
    (``Contract.payment.IBAN``, a ``coredata.PersonBank``).
    """

    dni = serializers.SerializerMethodField()
    nombre = serializers.SerializerMethodField()
    iban = serializers.SerializerMethodField()

    def get_dni(self, obj):
        if obj.dni:
            return obj.dni
        return obj.person.token if obj.person else None

    def get_nombre(self, obj):
        if obj.name:
            return obj.name
        if obj.person:
            parts = [part for part in (obj.person.name, obj.person.surname) if part]
            return " ".join(parts) if parts else None
        return None

    def get_iban(self, obj):
        return mask_iban(obj.iban)


class ContractListItemOVSerializer(serializers.Serializer):
    """
    One element of `GET /ov/contracts/` — see `ContractListItem` in
    `docs/ov/openapi.yaml`.

    Every field is a `SerializerMethodField` on purpose: DRF's nested
    ``source=`` traversal drops the key entirely when it walks into a null FK,
    which would break the always-present contract this endpoint documents.
    """

    token = serializers.SerializerMethodField()
    status_token = serializers.SerializerMethodField()
    status_name = serializers.SerializerMethodField()
    payment_type = serializers.SerializerMethodField()
    contract_holder = serializers.SerializerMethodField()
    direct_debit_holder = serializers.SerializerMethodField()
    allowed_actions = serializers.SerializerMethodField()
    is_account_holder = serializers.SerializerMethodField()

    def _request_dni(self):
        """DNI passat per query, normalitzat (`None` si no n'hi ha)."""
        request = self.context.get("request")
        if request is None:
            return None
        dni = (request.query_params.get("dni") or "").strip().upper()
        return dni or None

    @staticmethod
    def _iban(obj):
        return obj.payment.IBAN if obj.payment else None

    @staticmethod
    def _iban_holder_dni(iban):
        if not iban:
            return None
        dni = iban.dni or (iban.person.token if iban.person else None)
        if not dni:
            return None
        return str(dni).strip().upper()

    def get_token(self, obj):
        return obj.token

    def get_status_token(self, obj):
        return obj.status.token if obj.status else None

    def get_status_name(self, obj):
        return obj.status.name if obj.status else None

    def get_payment_type(self, obj):
        return obj.payment.type.token if obj.payment and obj.payment.type else None

    def get_contract_holder(self, obj):
        if not obj.holder:
            return None
        return ContractHolderOVSerializer(obj.holder).data

    def get_direct_debit_holder(self, obj):
        person_bank = obj.payment.IBAN if obj.payment else None
        if not person_bank:
            return None
        return ContractDebitHolderOVSerializer(person_bank).data

    def get_allowed_actions(self, obj):
        # TODO: the per-contract allow-list of actions is not defined yet, so no
        # action is advertised for any contract.
        return []

    def get_is_account_holder(self, obj):
        """`true` si el `dni` de la query coincide amb el titular del compte
        de domiciliació; `false` si el `dni` no hi és o no coincideix (la clau
        s'elimina del resultat quan no hi ha `dni`)."""
        dni = self._request_dni()
        if not dni:
            return False
        iban_dni = self._iban_holder_dni(self._iban(obj))
        if not iban_dni:
            return False
        return dni == iban_dni

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self._request_dni():
            data.pop("is_account_holder", None)
        return data


class ContractFullDetailSerializer(serializers.ModelSerializer):
    """Detalle completo de un contrato (contrato + facturación + datos de la
    cuenta de domiciliación). Corresponde al esquema `ContractFullDetail`."""

    status_token = serializers.CharField(source="status.token", read_only=True)
    status_name = serializers.CharField(source="status.name", read_only=True)
    holder_token = serializers.CharField(source="holder.token", read_only=True)
    payment_type = serializers.CharField(source="payment.type.token", read_only=True)
    use_type = serializers.CharField(source="use_type.name", read_only=True)
    last_invoice_date = serializers.SerializerMethodField()
    supply_point_address = serializers.SerializerMethodField()
    meter_serial_number = serializers.CharField(
        source="supply_point_default.meter.token", read_only=True
    )
    meter_caliber = serializers.CharField(
        source="supply_point_default.meter.caliber.name", read_only=True
    )
    smart_metering = serializers.SerializerMethodField()
    registration_date = serializers.SerializerMethodField()
    termination_date = serializers.SerializerMethodField()

    nif = serializers.CharField(source="holder.token", read_only=True)
    tenant_name = serializers.SerializerMethodField()
    holder_name = serializers.SerializerMethodField()
    city = serializers.CharField(
        source="supply_point_default.address.city.name", read_only=True
    )
    postal_code = serializers.CharField(
        source="supply_point_default.address.postal_code", read_only=True
    )
    paper_invoice = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    invoice_language = serializers.SerializerMethodField()
    phone1 = serializers.SerializerMethodField()
    phone2 = serializers.SerializerMethodField()

    account_holder_dni = serializers.SerializerMethodField()
    is_account_holder = serializers.SerializerMethodField()
    holder_address = serializers.SerializerMethodField()
    iban = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = [
            "token",
            "status_token",
            "status_name",
            "holder_token",
            "payment_type",
            "use_type",
            "last_invoice_date",
            "supply_point_address",
            "meter_serial_number",
            "meter_caliber",
            "smart_metering",
            "registration_date",
            "termination_date",
            "nif",
            "tenant_name",
            "holder_name",
            "city",
            "postal_code",
            "paper_invoice",
            "email",
            "invoice_language",
            "phone1",
            "phone2",
            "account_holder_dni",
            "is_account_holder",
            "holder_address",
            "iban",
        ]

    def _iban(self, obj):
        return obj.payment.IBAN if obj.payment and obj.payment.IBAN else None

    def get_registration_date(self, obj):
        if obj.registration_date:
            return obj.registration_date.strftime("%d/%m/%Y")
        return obj.created_at.strftime("%d/%m/%Y")

    def get_termination_date(self, obj):
        contract_termination_completed_token = ConfigProject.objects.get(token="contract_termination_completed_token").value
        contract_terminated_status = ConfigProject.objects.get(token="contract_terminated_status").value
        termination = ContractTerminationRequest.objects.filter(
            contract=obj,
            status__token=contract_termination_completed_token
        ).first()
        if termination and obj.status.token == contract_terminated_status:
            return termination.approved_at.strftime("%d/%m/%Y") if termination.approved_at else termination.created_at.strftime("%d/%m/%Y")
        return None

    def get_last_invoice_date(self, obj):
        last_invoice = obj.invoices.order_by("-created_at").first()
        if last_invoice:
            return last_invoice.created_at
        return None

    def get_supply_point_address(self, obj):
        supply_point = obj.supply_point_default
        if supply_point:
            return str(supply_point.address)
        return None

    def get_smart_metering(self, obj):
        supply_point = obj.supply_point_default
        if not supply_point or not supply_point.meter:
            return "false"
        return "true" if supply_point.meter.has_remote_reading else "false"

    def get_tenant_name(self, obj):
        if not obj.holder:
            return ""
        return f"{obj.holder.name} {obj.holder.surname}"

    def get_holder_name(self, obj):
        if not obj.holder:
            return ""
        return f"{obj.holder.name} {obj.holder.surname}"

    def get_email(self, obj):
        contact = obj.person_contact_email
        if contact:
            return contact.email
        return ""

    def get_phone1(self, obj):
        contact = (
            obj.contacts.filter(is_default=True)
            .exclude(phone__isnull=True)
            .exclude(phone__exact="")
            .first()
        )
        if not contact:
            contact = (
                obj.contacts.exclude(phone__isnull=True)
                .exclude(phone__exact="")
                .first()
            )
        return contact.phone if contact else ""

    def get_phone2(self, obj):
        contact = (
            obj.contacts.filter(is_default=False)
            .exclude(phone__isnull=True)
            .exclude(phone__exact="")
            .first()
        )
        if not contact:
            contact = (
                obj.contacts.exclude(phone__isnull=True).exclude(phone__exact="").last()
            )
        return contact.phone if contact else ""

    def get_paper_invoice(self, obj):
        communication_type = obj.communication_type
        return "true" if communication_type != "DIGITAL" else "false"

    def get_invoice_language(self, obj):
        return config("INVOICE_LANGUAGE", default="en")

    def get_account_holder_dni(self, obj):
        iban = self._iban(obj)
        if not iban:
            return None
        return iban.dni or (
            iban.person.token if iban.person and iban.person.token else None
        )

    def _request_dni(self):
        """DNI passat per query, normalitzat (`None` si no n'hi ha)."""
        request = self.context.get("request")
        if request is None:
            return None
        dni = (request.query_params.get("dni") or "").strip().upper()
        return dni or None

    @staticmethod
    def _iban_holder_dni(iban):
        if not iban:
            return None
        dni = iban.dni or (iban.person.token if iban.person else None)
        if not dni:
            return None
        return str(dni).strip().upper()

    def get_is_account_holder(self, obj):
        """`true` només si la query passa un `dni` que coincideix amb el
        titular del compte de domiciliació (normalitzat). Sense `dni` a la
        query la clau s'elimina del resultat."""
        dni = self._request_dni()
        if not dni:
            return False
        iban_dni = self._iban_holder_dni(self._iban(obj))
        if not iban_dni:
            return False
        return dni == iban_dni

    def get_holder_address(self, obj):
        holder = obj.holder
        if not holder:
            return None
        billing_address = (
            PersonAddress.objects.filter(person=holder, is_billing=True)
            .select_related("address")
            .first()
        )
        if billing_address and billing_address.address:
            return str(billing_address.address)
        return None

    def get_iban(self, obj):
        iban = self._iban(obj)
        iban_number = iban.iban if iban else None
        if not iban_number:
            return ""
        if self.get_is_account_holder(obj):
            return iban_number
        first_part = iban_number[:8]
        last_part = iban_number[-8:]
        masked_middle = "*" * (len(iban_number) - 16)
        return f"{first_part}{masked_middle}{last_part}"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self._request_dni():
            data.pop("is_account_holder", None)
        return data


class InvoiceFullDetailSerializer(serializers.ModelSerializer):
    """Detalle completo de una factura definitiva. Corresponde al esquema
    `InvoiceFullDetail` del documento OpenAPI (`GET /ov/invoice/{token}/detail/`)."""

    contract_number = serializers.CharField(source="contract.token", read_only=True)
    invoice_token = serializers.CharField(source="token", read_only=True)
    invoice_number = serializers.CharField(source="serie_final", read_only=True)
    invoice_date = serializers.DateField(source="issue_date", read_only=True)
    invoice_status = serializers.CharField(source="status.name", read_only=True)
    due_date = serializers.DateField(read_only=True, allow_null=True)
    invoice_amount = serializers.FloatField(source="left_to_pay", read_only=True)
    total_amount = serializers.FloatField(source="total_final", read_only=True)
    subtotal_amount = serializers.FloatField(source="subtotal_final", read_only=True)
    payment_method = serializers.CharField(source="payment_type_final", read_only=True, allow_null=True)
    pdf_available = serializers.SerializerMethodField()
    billing_period = serializers.SerializerMethodField()
    dwelling_code = serializers.SerializerMethodField()
    tax_address = serializers.SerializerMethodField()
    tariffs = serializers.SerializerMethodField()
    fiscal_breakdown = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "contract_number",
            "invoice_token",
            "invoice_number",
            "invoice_date",
            "invoice_status",
            "due_date",
            "invoice_amount",
            "total_amount",
            "subtotal_amount",
            "payment_method",
            "pdf_available",
            "billing_period",
            "dwelling_code",
            "tax_address",
            "tariffs",
            "fiscal_breakdown",
        ]

    def _direct_debit_token(self):
        cfg = ConfigProject.objects.filter(token="direct_debit_token").first()
        return cfg.value if cfg and cfg.value else "DIRECT_DEBIT"

    def get_pdf_available(self, obj):
        date_str = ConfigProject.objects.filter(token="ov_pdf_from").first()
        if not date_str or not date_str.value:
            return True
        pdf_from_date = parse_date(date_str.value)
        if obj.issue_date and pdf_from_date and obj.issue_date < pdf_from_date:
            return False
        return True

    def get_billing_period(self, obj):
        return {
            "year": obj.billing_period_year,
            "month": obj.billing_period_month,
            "days": obj.billing_period_days,
        }

    def get_dwelling_code(self, obj):
        return None

    def get_tax_address(self, obj):
        if obj.payment_type_token_final != self._direct_debit_token():
            return None
        is_anonymized = bool(
            obj.payer_token_final
            and obj.customer_token_final
            and obj.payer_token_final != obj.customer_token_final
        )
        payload = {
            "is_anonymized": is_anonymized,
            "postal_code": obj.postal_code_final or "",
            "city": obj.city_final or "",
            "province": obj.province_final,
            "country": obj.country_final,
        }
        if not is_anonymized:
            payload["address"] = obj.address_final
        return payload

    def get_tariffs(self, obj):
        tariffs = []
        line_items = obj.line_items.select_related(
            "price_rate__billing_range_active__publication", "company"
        ).order_by("custom_order", "id")
        for line in line_items:
            publication = None
            price_rate = line.price_rate
            if price_rate and price_rate.billing_range_active:
                publication = price_rate.billing_range_active.publication
            normativa = None
            if publication:
                normativa = {
                    "reference": publication.reference or "",
                    "name": publication.name,
                }
            tariffs.append(
                {
                    "name": line.price_rate_name or line.name,
                    "description": line.description,
                    "units": line.units,
                    "unit_price": line.price,
                    "tax_percent": line.tax_percent,
                    "total": float(line.total),
                    "normativa": normativa,
                }
            )
        return tariffs

    def get_fiscal_breakdown(self, obj):
        totals = {}
        line_items = obj.line_items.select_related(
            "company", "price_rate__product__company"
        ).all()
        for line in line_items:
            company = None
            if line.company and line.company.name:
                company = line.company.name
            elif (
                line.price_rate
                and line.price_rate.product
                and line.price_rate.product.company
                and line.price_rate.product.company.name
            ):
                company = line.price_rate.product.company.name
            if not company:
                continue
            totals[company] = totals.get(company, 0.0) + float(line.total)
        return [
            {"organization": org, "amount": round(amount, 2)}
            for org, amount in sorted(totals.items())
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get("tax_address") is None:
            data.pop("tax_address", None)
        return data


class MeterDetailSerializer(serializers.ModelSerializer):
    """Detalle del contador de un contrato. Corresponde al esquema `MeterDetail`
    del documento OpenAPI (`GET /ov/meter/{token}/`). El `token` de la ruta es el
    del contrato; los cinco campos se resuelven desde `supply_point_default.meter`
    y devuelven `None` si no hay punto de suministro por defecto ni contador."""

    meter_serial_number = serializers.SerializerMethodField()
    meter_caliber = serializers.SerializerMethodField()
    digits = serializers.SerializerMethodField()
    manufacture_year = serializers.SerializerMethodField()
    installation_date = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = [
            "meter_serial_number",
            "meter_caliber",
            "digits",
            "manufacture_year",
            "installation_date",
        ]

    @staticmethod
    def _meter(obj):
        supply_point = obj.supply_point_default
        return supply_point.meter if supply_point else None

    def get_meter_serial_number(self, obj):
        meter = self._meter(obj)
        return meter.token if meter else None

    def get_meter_caliber(self, obj):
        meter = self._meter(obj)
        if not meter or not meter.caliber:
            return None
        return meter.caliber.name

    def get_digits(self, obj):
        meter = self._meter(obj)
        return meter.digits if meter else None

    def get_manufacture_year(self, obj):
        meter = self._meter(obj)
        return meter.manufacturing_year if meter else None

    def get_installation_date(self, obj):
        meter = self._meter(obj)
        return meter.installation_at if meter else None


def _hf_quarter(month):
    """T1=gen-mar, T2=abr-jun, T3=jul-set, T4=oct-des."""
    if not month:
        return None
    return min(4, max(1, (int(month) - 1) // 3 + 1))


class ConsumptionHistoryItemSerializer(serializers.ModelSerializer):
    """Correspon a l'esquema `ConsumptionHistoryItem` de l'OpenAPI
    (`GET /ov/consumptions/`). El `period` s'obté del `billing_period` de la
    factura vinculada quan n'hi ha i, si no, del trimestre natural de la
    `reading_date` (nomenclatura HF `{any}-{q}T`)."""

    period = serializers.SerializerMethodField()
    reading = serializers.FloatField(source="reading_value", read_only=True, allow_null=True)
    consumption = serializers.FloatField(source="real_consumption", read_only=True, allow_null=True)
    reading_date = serializers.DateField(read_only=True, allow_null=True)
    is_estimated = serializers.BooleanField(read_only=True)
    previous_reading = serializers.SerializerMethodField()

    class Meta:
        model = Reading
        fields = [
            "id",
            "period",
            "reading",
            "previous_reading",
            "consumption",
            "reading_date",
            "is_estimated",
        ]

    def get_period(self, obj):
        # 1) invocada: invoice billing_period_year/month -> "{year}-{q}T"
        for inv in obj.invoices.all():
            if inv.billing_period_year and inv.billing_period_month:
                q = _hf_quarter(inv.billing_period_month)
                if q:
                    return f"{inv.billing_period_year}-{q}T"
        # 2) fallback: reading_date -> "{year}-{q}T"
        if obj.reading_date:
            q = _hf_quarter(obj.reading_date.month)
            if q:
                return f"{obj.reading_date.year}-{q}T"
        return None

    def get_previous_reading(self, obj):
        if not obj.previous_reading or obj.previous_reading.reading_value is None:
            return None
        return float(obj.previous_reading.reading_value)


class ConsumptionDownloadRequestSerializer(serializers.Serializer):
    """Cuerpo JSON de `POST /ov/consumptions/download/`. Corresponde al esquema
    `ConsumptionDownloadRequest` del documento OpenAPI."""

    contract_token = serializers.CharField(required=True)
    reading_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=True
    )
    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)
    format = serializers.ChoiceField(
        choices=[("pdf", "pdf"), ("csv", "csv"), ("zip", "zip")],
        required=False,
        default="pdf",
    )

    def validate(self, data):
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                {"date_from": "La fecha de inicio no puede ser posterior a la final"}
            )
        return data


class BillingPeriodItemSerializer(serializers.Serializer):
    """Elemento del listado de periodos de facturación disponibles para el
    contrato (`GET /ov/billing-periods/`). Los ciclos de facturación los define
    el PA (trimestral, bimestral, etc.) y el frontal no puede hardcodearlos.
    Corresponde al esquema `BillingPeriodItem` del documento OpenAPI."""

    year = serializers.IntegerField()
    period_code = serializers.CharField()
    months_label = serializers.CharField()
    is_current = serializers.BooleanField()


class SepaDocumentUploadSerializer(serializers.Serializer):
    """Valida el upload del mandato SEPA firmado (multipart/form-data):
    el documento (`sepa`) y el IBAN de la cuenta de domiciliación (`iban`)."""

    sepa = serializers.FileField(required=True)
    iban = serializers.CharField(required=True)

    def validate_iban(self, value):
        # Limpia espacios (en blanco por agrupación) y normaliza a mayúsculas
        return "".join(value.split()).upper()

    def validate_sepa(self, value):
        if not value:
            raise serializers.ValidationError("File is required")
        name = str(value.name or "").lower()
        if not (
            name.endswith(".pdf")
            or name.endswith((".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp", ".webp", ".heic"))
        ):
            raise serializers.ValidationError(
                "Invalid file type. Only PDF or image files are allowed."
            )
        return value


class CancelDirectDebitSerializer(serializers.Serializer):
    """Valida la sol·licitud de cancel·lació de domiciliació (revocació
    del mandat SEPA i canvi de la forma de pagament del contracte).

    - `period`: període de facturació des del qual s'aplica la cancel·lació
      (p. ex. "2026-3T").
    - `role`: rol de qui sol·licita (p. ex. "TITULAR", "PAGADOR").
    - `new_payment_type`: token del nou tipus de pagament demanat; opcional.
      Si falta, es fa servir el tipus per defecte `BANK_TRANSFER`.
    """

    period = serializers.CharField(required=True)
    role = serializers.CharField(required=True)
    new_payment_type = serializers.CharField(required=False)


class ContactDataOVSerializer(BillingDataOVSerializer):
    """Extén `BillingDataOVSerializer` (configuración del perfil) amb
    l'adreça postal del titular del contracte (`holder_address`)."""

    holder_address = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = BillingDataOVSerializer.Meta.fields + ["holder_address"]

    def get_holder_address(self, obj):
        holder = obj.holder
        if not holder:
            return None
        billing_address = (
            PersonAddress.objects.filter(person=holder, is_billing=True)
            .select_related("address")
            .first()
        )
        if billing_address and billing_address.address:
            return str(billing_address.address)
        return None


