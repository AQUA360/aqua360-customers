#!/usr/bin/env python3
"""
Django management command per provar la funció get_average_consumption.

Ús:
    python manage.py test_average_consumption --contract-id <id>
    python manage.py test_average_consumption --contract-id <id> --month 12
"""

from django.core.management.base import BaseCommand, CommandError
from contract.models import Contract
from billing.utils.reading_service import get_average_consumption
from statistics.models import ContractConsumption


class Command(BaseCommand):
    help = 'Prova la funció get_average_consumption per un contracte específic'

    def add_arguments(self, parser):
        parser.add_argument(
            '--contract-id',
            type=int,
            default=1931,
            help='ID del contracte a provar (per defecte: 1931)'
        )
        parser.add_argument(
            '--month',
            type=int,
            default=12,
            help='Mes a provar (1-12, per defecte: 12)'
        )

    def handle(self, *args, **options):
        contract_id = options['contract_id']
        month = options['month']
        
        # Validar el mes
        if month < 1 or month > 12:
            raise CommandError(f"El mes ha de ser entre 1 i 12. S'ha proporcionat: {month}")
        
        # Obtenir el contracte
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            raise CommandError(f"No s'ha trobat cap contracte amb id={contract_id}")
        
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Provant get_average_consumption")
        self.stdout.write(f"{'='*60}")
        self.stdout.write(f"Contracte ID: {contract.id}")
        if contract.token:
            self.stdout.write(f"Contracte Token: {contract.token}")
        self.stdout.write(f"Mes inicial: {month}")
        self.stdout.write(f"{'='*60}\n")
        
        # Mostrar ContractConsumption existents per aquest contracte
        consumptions = ContractConsumption.objects.filter(contract=contract).order_by('period')
        if consumptions.exists():
            self.stdout.write(f"ContractConsumption existents per al contracte {contract.id}:")
            for cc in consumptions:
                self.stdout.write(f"  Mes {cc.period}: {cc.consumption}")
        else:
            self.stdout.write(self.style.WARNING(f"No hi ha ContractConsumption per al contracte {contract.id}"))
        
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("Executant get_average_consumption...")
        self.stdout.write(f"{'='*60}\n")
        
        # Executar la funció
        result = get_average_consumption(contract, month)
        
        # Mostrar el resultat
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("RESULTAT:")
        self.stdout.write(f"{'='*60}")
        if result is not None:
            self.stdout.write(self.style.SUCCESS(f"Consum mitjà trobat: {result}"))
        else:
            self.stdout.write(self.style.WARNING("No s'ha trobat cap consum mitjà vàlid"))
        self.stdout.write(f"{'='*60}\n")

