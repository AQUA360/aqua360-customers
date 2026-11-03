from django.db import models


class SendBatchProvider(models.Model):
    """Integració destí dels lots (Odoo, …)."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["position", "token"]

    def __str__(self):
        return self.name or self.token


class SendBatchType(models.Model):
    """
    Tipus de lot d'enviament (invoices, payments, commitment_*).

    `provider` identifica la integració destí perquè el mateix token de tipus
    pugui existir en més d'un sistema amb endpoints diferents.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    provider = models.ForeignKey(
        SendBatchProvider,
        on_delete=models.PROTECT,
        related_name="batch_types",
        help_text="Integració destí del lot (determina client/base URL).",
    )
    token = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    endpoint = models.CharField(
        max_length=255,
        help_text="Ruta relativa del proveïdor, p.ex. /batch/invoices",
    )
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Tipus per defecte dins d'aquest provider (p.ex. invoices Odoo).",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "token"],
                name="uniq_sendbatchtype_provider_token",
            ),
        ]
        ordering = ["provider", "position", "token"]

    def __str__(self):
        label = self.name or self.token
        provider = self.provider.token if self.provider_id else None
        return f"{provider}:{label}" if provider else label


class SendBatchStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "SendBatchStatus ID {}".format(self.token)


class SendBatch(models.Model):
    """
    Lot d'enviament bulk (fins a 1000 documents).

    La resposta immediata (202/200/422…) es desa a l'instant; la resposta final
    arriba més tard via inbound (mateix JSON que GET /aqua360/batch/{batch_id}).
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(
        max_length=64,
        unique=True,
        help_text="batch_id enviat a Odoo (1-64: [A-Za-z0-9._-]).",
    )
    batch_type = models.ForeignKey(
        SendBatchType, on_delete=models.PROTECT, related_name="batches"
    )
    billing = models.ForeignKey(
        "billing.Billing",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="send_batches",
    )
    invoices = models.ManyToManyField(
        "billing.Invoice", blank=True, related_name="send_batches"
    )
    commitment_deposits = models.ManyToManyField(
        "billing.CommitmentDeposit", blank=True, related_name="send_batches"
    )
    payments = models.ManyToManyField(
        "billing.PaymentMovement",
        blank=True,
        related_name="send_batches",
        help_text="PaymentMovements enviats com a pagaments/cobraments.",
    )
    related_batch = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resend_batches",
        help_text="Lot original quan aquest és un reenviament d'errors.",
    )

    # Resposta immediata de l'enviament (acceptació del lot)
    sent_at = models.DateTimeField(null=True, blank=True)
    instant_status_code = models.IntegerField(null=True, blank=True)
    instant_response = models.JSONField(null=True, blank=True)

    # Resposta final (inbound o consulta GET)
    status = models.ForeignKey(
        SendBatchStatus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batches",
    )
    received_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    summary = models.JSONField(null=True, blank=True)
    final_response = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Send batch"
        verbose_name_plural = "Send batches"

    def __str__(self):
        return self.token or f"SendBatch {self.pk}"


class SendBatchObservation(models.Model):
    send_batch = models.ForeignKey(
        SendBatch,
        on_delete=models.CASCADE,
        related_name="observations",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    status = models.ForeignKey(
        SendBatchStatus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status_name = models.CharField(max_length=255, null=True, blank=True)
    is_important = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        if self.observation:
            return self.observation
        return f"SendBatchObservation {self.id}"


class IntegrationRequestLog(models.Model):
    DIRECTION_INBOUND = "inbound"
    DIRECTION_OUTBOUND = "outbound"

    DIRECTION_CHOICES = [
        (DIRECTION_INBOUND, "Inbound"),
        (DIRECTION_OUTBOUND, "Outbound"),
    ]

    provider = models.CharField(max_length=100)
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    method = models.CharField(max_length=10)
    endpoint = models.CharField(max_length=255)
    request_payload = models.JSONField(null=True, blank=True)
    response_payload = models.JSONField(null=True, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider} {self.method} {self.endpoint} ({self.success})"


class ContractSigningSession(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SIGNED = "signed"
    STATUS_EXPIRED = "expired"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SIGNED, "Signed"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_FAILED, "Failed"),
    ]

    contract_request = models.ForeignKey(
        "contract.ContractRequest",
        on_delete=models.CASCADE,
        related_name="signing_sessions",
    )
    session_id = models.CharField(max_length=36, unique=True)
    external_reference = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    signing_url = models.URLField(max_length=500, blank=True)
    recipient_name = models.CharField(max_length=255)
    recipient_email = models.EmailField()
    recipient_phone = models.CharField(max_length=50, blank=True)
    callback_url = models.URLField(max_length=500, blank=True)
    email_sent = models.BooleanField(default=False)
    signed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Signing {self.session_id} ({self.status})"
