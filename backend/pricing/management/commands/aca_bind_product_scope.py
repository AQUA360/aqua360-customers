"""Lliga el producte estàndard del cànon de l'aigua (ACA) a l'empresa i l'explotació.

El fixture `initial_data/ca/optional/pricing.ACA.json` NO entra amb el `loaddata
initial_data/ca/*.json` general: és OPCIONAL i només es carrega a les instal·lacions NOVES, amb una
línia pròpia a l'`init.sh` (els clients que ja tenen el seu propi cànon en tindrien dos). Quan es
carrega, encara no existeix cap `Exploitation` ni cap `Company`: per això el producte hi va amb
`company` i `exploitation` a NULL. Aquesta comanda els hi assigna un cop importades les
explotacions, i deixa també apuntat el `ConfigProject` `token_product_aca` cap al producte.

Ordre a l'`init.sh`: DESPRÉS de `import_gen_exploitations` i ABANS de qualsevol import de
contractes o factures que hagi de resoldre tarifes del cànon.

    python3 manage.py aca_bind_product_scope [--exploitation-token X] [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from coredata.models import ConfigProject
from pricing.models import Product
from service.models import Company, Exploitation

ACA_PRODUCT_TOKEN = 'ACA-CANON'
ACA_PRODUCT_CONFIG_TOKEN = 'token_product_aca'


class Command(BaseCommand):
    help = "Assigna empresa i explotació al producte estàndard del cànon ACA."

    def add_arguments(self, parser):
        parser.add_argument('--product-token', default=ACA_PRODUCT_TOKEN)
        parser.add_argument(
            '--exploitation-token',
            help="Explotació a la qual lligar el producte. Per defecte, l'única que hi ha; "
                 "en una instal·lació amb diverses explotacions és OBLIGATORI indicar-la.")
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        token = options['product_token']
        dry_run = options['dry_run']

        products = list(Product.objects.filter(token=token))
        if not products:
            self.stdout.write(self.style.ERROR(
                f"No hi ha cap Product amb token «{token}»: el fixture optional/pricing.ACA.json no s'ha "
                f"carregat."))
            return
        if len(products) > 1:
            self.stdout.write(self.style.ERROR(
                f"Hi ha {len(products)} productes amb token «{token}». L'app els resol per token: "
                f"cal deixar-ne un de sol abans de continuar."))
            return
        product = products[0]

        exploitations = list(Exploitation.objects.all().order_by('id'))
        wanted = options.get('exploitation_token')
        if wanted:
            exploitation = next((e for e in exploitations if e.token == wanted), None)
            if exploitation is None:
                self.stdout.write(self.style.ERROR(
                    f"No hi ha cap explotació amb token «{wanted}»."))
                return
        elif len(exploitations) == 1:
            exploitation = exploitations[0]
        elif not exploitations:
            self.stdout.write(self.style.ERROR(
                "No hi ha cap explotació: executa abans import_gen_exploitations."))
            return
        else:
            self.stdout.write(self.style.ERROR(
                f"Hi ha {len(exploitations)} explotacions "
                f"({', '.join(e.token or str(e.id) for e in exploitations)}): cal indicar "
                f"--exploitation-token."))
            return

        company = getattr(exploitation, 'company', None) or Company.objects.order_by('id').first()
        if company is None:
            self.stdout.write(self.style.ERROR("No hi ha cap empresa (Company) a la instal·lació."))
            return

        self.stdout.write(
            f"Producte «{product.name}» ({product.token}) → explotació {exploitation.token}, "
            f"empresa {company.id}")
        if dry_run:
            self.stdout.write(self.style.WARNING("--dry-run: no s'ha desat res."))
            return

        with transaction.atomic():
            product.exploitation = exploitation
            product.company = company
            product.save(update_fields=['exploitation', 'company', 'updated_at'])
            config, created = ConfigProject.objects.get_or_create(
                token=ACA_PRODUCT_CONFIG_TOKEN,
                defaults={'value': product.token, 'name': 'Token del producte del cànon (ACA)'})
            if not created and (config.value or '').strip() != product.token:
                previous = config.value
                config.value = product.token
                config.save(update_fields=['value'])
                self.stdout.write(
                    f"ConfigProject «{ACA_PRODUCT_CONFIG_TOKEN}»: {previous!r} → {product.token!r}")

        self.stdout.write(self.style.SUCCESS("Fet."))
