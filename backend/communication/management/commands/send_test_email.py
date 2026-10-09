#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import urllib.error

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError


def _mask(value: str, keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return f"{value[:keep]}{'*' * (len(value) - keep)}"


def _decode_jwt_payload(token: str) -> dict:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload + padding)
        data = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _patch_httperror_add_note() -> None:
    """django-msgraphbackend 1.0.x fa err.add_note(); a Python 3.10 HTTPError
    delega l'atribut a HTTPResponse i amaga l'error real de Graph."""
    existing = getattr(urllib.error.HTTPError, "add_note", None)
    if existing is not None and getattr(existing, "__msgraph_compat__", False):
        return
    if getattr(Exception, "add_note", None) is not None:
        return

    def add_note(self, note):
        notes = getattr(self, "__notes__", None)
        if notes is None:
            self.__notes__ = []
            notes = self.__notes__
        notes.append(note)

    add_note.__msgraph_compat__ = True
    urllib.error.HTTPError.add_note = add_note


def _graph_error_details(exc: BaseException) -> str:
    parts = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, urllib.error.HTTPError):
            # HTTPError hereta addinfourl: atributs inexistent van al
            # HTTPResponse intern (full_url, etc.) i peten. URL i cos
            # estan a filename / __dict__, no via __getattr__.
            code = current.__dict__.get("code", "?")
            reason = current.__dict__.get("msg") or current.__dict__.get("reason") or ""
            parts.append(f"HTTP {code} {reason}".strip())
            url = current.__dict__.get("filename")
            if url:
                parts.append(f"URL: {url}")
            notes = current.__dict__.get("__notes__") or []
            for note in notes:
                parts.append(str(note))
        current = current.__context__ or current.__cause__
    return "\n".join(parts)


class Command(BaseCommand):
    help = "Envia un email de prova amb la configuració actual (SMTP o Microsoft Graph)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            required=True,
            help="Email destinatari (ex: prova@domini.cat).",
        )
        parser.add_argument(
            "--subject",
            default="[TEST] Enviament email (Django)",
            help="Assumpte del correu.",
        )
        parser.add_argument(
            "--body",
            default="Aquest és un correu de prova enviat des d'un management command de Django.",
            help="Cos del missatge.",
        )
        parser.add_argument(
            "--from-email",
            dest="from_email",
            default="",
            help="Remitent. Si no s'indica, s'usa DEFAULT_FROM_EMAIL o SERVER_EMAIL.",
        )
        parser.add_argument(
            "--show-traceback",
            action="store_true",
            help="Mostra el traceback complet si hi ha error enviant.",
        )
        parser.add_argument(
            "--config-token",
            dest="config_token",
            default="",
            help=(
                "CompanyConfig.token (cerca a BD). Ajusta remitent i, només si "
                "EMAIL_BACKEND és SMTP, host/port/usuari/TLS. El backend i secrets "
                "(Graph o contrasenya SMTP) venen dels settings /.env, igual que "
                "a communication_service."
            ),
        )

    def handle(self, *args, **options):
        to_email = options["to"].strip()
        subject = options["subject"]
        body = options["body"]
        from_email = (options.get("from_email") or "").strip()
        config_token = (options.get("config_token") or "").strip()

        if not to_email or "@" not in to_email:
            raise CommandError(f"Destinatari invàlid: {to_email!r}")

        backend = getattr(settings, "EMAIL_BACKEND", "")
        email_use_tls = getattr(settings, "EMAIL_USE_TLS", None)
        email_use_ssl = getattr(settings, "EMAIL_USE_SSL", None)
        email_host = getattr(settings, "EMAIL_HOST", "")
        email_port = getattr(settings, "EMAIL_PORT", "")
        email_user = getattr(settings, "EMAIL_HOST_USER", "")
        email_password = getattr(settings, "EMAIL_HOST_PASSWORD", "")
        default_from = getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "SERVER_EMAIL", "")
        config = None

        if config_token:
            from service.models import CompanyConfig

            try:
                config = CompanyConfig.objects.get(token=config_token)
            except CompanyConfig.DoesNotExist as exc:
                raise CommandError(
                    f"No existeix cap CompanyConfig amb token {config_token!r}."
                ) from exc
            except CompanyConfig.MultipleObjectsReturned as exc:
                raise CommandError(
                    f"Hi ha més d'un CompanyConfig amb token {config_token!r}. El token ha de ser únic."
                ) from exc

            # Remitent des de BD (mateix patró que communication_service amb comm_config).
            default_from = config.company_config_emails.filter(is_default=True).first().mail_send_user or default_from

            # EMAIL_BACKEND sempre des de settings /.env — no es força SMTP via CompanyConfig.
            if backend != "msgraphbackend.MSGraphBackend":
                email_host = config.mail_send_smtp_server or email_host
                email_port = config.mail_send_smtp_port or email_port
                email_user = config.company_config_emails.filter(is_default=True).first().mail_send_mail or email_user
                if config.use_TLS is not None:
                    email_use_tls = config.use_TLS
                if config.use_SSL is not None:
                    email_use_ssl = config.use_SSL
                # Igual que _send_via_smtp: contrasenya des d'atribut de settings (token) o EMAIL_HOST_PASSWORD.
                email_password = (
                    getattr(settings, config.token, None)
                    if config.token
                    else getattr(settings, "EMAIL_HOST_PASSWORD", "")
                )
                if not email_password:
                    email_password = getattr(settings, "EMAIL_HOST_PASSWORD", "")

        if not from_email:
            from_email = default_from

        if not from_email:
            raise CommandError(
                "No hi ha remitent. Defineix --from-email o configura DEFAULT_FROM_EMAIL/SERVER_EMAIL."
            )

        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write("Configuració email detectada")
        self.stdout.write("=" * 70)
        self.stdout.write(f"EMAIL_BACKEND: {backend}")
        if config:
            self.stdout.write(f"CONFIG_TOKEN: {config_token}")
        self.stdout.write(f"From: {from_email}")
        self.stdout.write(f"To: {to_email}")

        graph_connection = None
        if backend == "msgraphbackend.MSGraphBackend":
            tenant = getattr(settings, "MSGRAPH_TENANT_ID", "")
            client_id = getattr(settings, "MSGRAPH_CLIENT_ID", "")
            user_id = getattr(settings, "MSGRAPH_USER_ID", "")
            client_secret = getattr(settings, "MSGRAPH_CLIENT_SECRET", "")

            self.stdout.write("")
            self.stdout.write("Microsoft Graph:")
            self.stdout.write(f"  MSGRAPH_TENANT_ID: {_mask(tenant)}")
            self.stdout.write(f"  MSGRAPH_CLIENT_ID: {_mask(client_id)}")
            self.stdout.write(f"  MSGRAPH_USER_ID: {_mask(user_id)} (opcional)")
            self.stdout.write(
                f"  MSGRAPH_CLIENT_SECRET: {'[set]' if bool(client_secret) else '[missing]'}"
            )
            if not tenant or not client_id or not client_secret:
                raise CommandError(
                    "Falten variables per Microsoft Graph. Cal MSGRAPH_TENANT_ID, MSGRAPH_CLIENT_ID i MSGRAPH_CLIENT_SECRET."
                )
            if user_id:
                self.stdout.write(
                    f"  Endpoint: POST /v1.0/users/{_mask(user_id)}/sendMail"
                )
                self.stdout.write(
                    "  El From ha de ser una adreça d'aquesta bústia (UPN o alias)."
                )
            else:
                self.stdout.write(
                    "  Endpoint: POST /v1.0/users/{id de From}/sendMail "
                    "(requereix User.Read.All per resoldre l'id)"
                )

            _patch_httperror_add_note()
            graph_connection = get_connection(backend=backend, fail_silently=False)
            graph_connection.open()
            token = getattr(getattr(graph_connection, "_token", None), "access_token", "")
            payload = _decode_jwt_payload(token) if token else {}
            roles = payload.get("roles") or []
            scp = payload.get("scp") or ""
            self.stdout.write("")
            self.stdout.write("  Token (client_credentials):")
            self.stdout.write(
                f"    roles (application): {', '.join(roles) if roles else '[cap]'}"
            )
            self.stdout.write(
                f"    scp (delegated): {scp if scp else '[cap]'}"
            )
            if "Mail.Send" not in roles:
                self.stdout.write("")
                self.stdout.write(
                    self.style.WARNING(
                        "  ATENCIÓ: el token NO té el rol d'aplicació Mail.Send.\n"
                        "  A Entra cal Microsoft Graph → Application permissions → Mail.Send\n"
                        "  (no Delegated) i Grant admin consent. Un permís delegat no entra\n"
                        "  al token de client_credentials i Graph respon 403."
                    )
                )
        else:
            self.stdout.write("")
            self.stdout.write("SMTP:")
            if email_host:
                self.stdout.write(f"  EMAIL_HOST: {email_host}")
            if email_port:
                self.stdout.write(f"  EMAIL_PORT: {email_port}")
            if email_use_tls is not None:
                self.stdout.write(f"  EMAIL_USE_TLS: {email_use_tls}")
            if email_user:
                self.stdout.write(f"  EMAIL_HOST_USER: {email_user}")
            self.stdout.write(
                f"  EMAIL_HOST_PASSWORD: {'[set]' if bool(email_password) else '[missing]'}"
            )
            if email_use_ssl is not None:
                self.stdout.write(f"  EMAIL_USE_SSL: {email_use_ssl}")
            if not email_host:
                raise CommandError("Falta EMAIL_HOST (o mail_send_smtp_server a CompanyConfig).")
            if not email_user:
                raise CommandError("Falta EMAIL_HOST_USER (o mail_send_mail a CompanyConfig).")
            if not email_password:
                raise CommandError("Falta EMAIL_HOST_PASSWORD a l'entorn (.env).")
            if not email_port:
                raise CommandError("Falta EMAIL_PORT (o mail_send_smtp_port a CompanyConfig).")

        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write("Enviant...")
        self.stdout.write("=" * 70)

        try:
            connection = graph_connection
            if backend != "msgraphbackend.MSGraphBackend":
                connection = get_connection(
                    backend=backend,
                    fail_silently=False,
                    host=email_host,
                    port=email_port,
                    username=email_user,
                    password=email_password,
                    use_tls=bool(email_use_tls),
                    use_ssl=bool(email_use_ssl),
                )
            msg = EmailMessage(
                subject=subject,
                body=body,
                from_email=from_email,
                to=[to_email],
                connection=connection,
            )
            sent = msg.send(fail_silently=False)
        except Exception as e:
            if options.get("show_traceback"):
                import traceback

                self.stdout.write("\nTraceback:")
                self.stdout.write(traceback.format_exc())
            graph_details = _graph_error_details(e)
            if graph_details:
                self.stdout.write("\nError Microsoft Graph:")
                self.stdout.write(graph_details)
            raise CommandError(f"Error enviant email: {type(e).__name__}: {e}") from e

        if sent != 1:
            raise CommandError(f"L'enviament no ha retornat èxit (send()={sent}).")

        self.stdout.write(self.style.SUCCESS("✅ Email enviat correctament."))
