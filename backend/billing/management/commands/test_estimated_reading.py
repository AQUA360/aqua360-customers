#!/usr/bin/env python3
"""
Django management command per provar la funció get_estimated_reading_minimal_object.

Ús:
    python manage.py test_estimated_reading --contract-id <id> --supply-point-id <id>
    python manage.py test_estimated_reading --contract-id <id> --supply-point-id <id> --date 2024-12-01
    python manage.py test_estimated_reading --contract-id <id> --supply-point-id <id> --date 2024-12-01 --batch-id <id>
"""

from datetime import datetime, date
from django.core.management.base import BaseCommand, CommandError
from contract.models import Contract
from service.models import SupplyPoint
from billing.models import ReadingBatch
from billing.utils.reading_service import get_estimated_reading_minimal_object
from statistics.models import ContractConsumption


class Command(BaseCommand):
    help = 'Prova la funció get_estimated_reading_minimal_object per un contracte i supply point específics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--contract-id',
            type=int,
            required=True,
            help='ID del contracte'
        )
        parser.add_argument(
            '--supply-point-id',
            type=int,
            required=True,
            help='ID del supply point'
        )
        parser.add_argument(
            '--date',
            type=str,
            default=None,
            help='Data per a la lectura estimada (format: YYYY-MM-DD). Per defecte: avui'
        )
        parser.add_argument(
            '--batch-id',
            type=int,
            default=None,
            help='ID del ReadingBatch (opcional)'
        )

    def handle(self, *args, **options):
        contract_id = options['contract_id']
        supply_point_id = options['supply_point_id']
        date_str = options['date']
        batch_id = options['batch_id']
        
        # Obtenir el contracte
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            raise CommandError(f"No s'ha trobat cap contracte amb id={contract_id}")
        
        # Obtenir el supply point
        try:
            supply_point = SupplyPoint.objects.get(id=supply_point_id)
        except SupplyPoint.DoesNotExist:
            raise CommandError(f"No s'ha trobat cap supply point amb id={supply_point_id}")
        
        # Validar que el supply point estigui relacionat amb el contracte
        if contract not in supply_point.contracts.all():
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  AVÍS: El supply point {supply_point_id} no està relacionat amb el contracte {contract_id}"
                )
            )
        
        # Processar la data
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                raise CommandError(f"Format de data invàlid: {date_str}. Utilitza el format YYYY-MM-DD")
        else:
            target_date = date.today()
        
        # Obtenir el batch (opcional)
        batch = None
        if batch_id:
            try:
                batch = ReadingBatch.objects.get(id=batch_id)
            except ReadingBatch.DoesNotExist:
                raise CommandError(f"No s'ha trobat cap ReadingBatch amb id={batch_id}")
        
        # Mostrar informació inicial
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Provant get_estimated_reading_minimal_object")
        self.stdout.write(f"{'='*60}")
        self.stdout.write(f"Contracte ID: {contract.id}")
        if contract.token:
            self.stdout.write(f"Contracte Token: {contract.token}")
        self.stdout.write(f"Supply Point ID: {supply_point.id}")
        if supply_point.name:
            self.stdout.write(f"Supply Point Name: {supply_point.name}")
        if supply_point.token:
            self.stdout.write(f"Supply Point Token: {supply_point.token}")
        self.stdout.write(f"Data: {target_date}")
        if batch:
            self.stdout.write(f"Batch ID: {batch.id}")
            if batch.name:
                self.stdout.write(f"Batch Name: {batch.name}")
        else:
            self.stdout.write(f"Batch: None")
        self.stdout.write(f"{'='*60}\n")
        
        # Mostrar informació del contracte
        if contract.created_at:
            contract_date = contract.created_at.date() if hasattr(contract.created_at, 'date') else contract.created_at
            self.stdout.write(f"Data de creació del contracte: {contract_date}")
        
        # Mostrar ContractConsumption per al mes de la data
        month = target_date.month
        consumptions = ContractConsumption.objects.filter(contract=contract, period=month)
        if consumptions.exists():
            self.stdout.write(f"\nContractConsumption per al mes {month}:")
            for cc in consumptions:
                self.stdout.write(f"  Mes {cc.period}: {cc.consumption}")
        else:
            self.stdout.write(self.style.WARNING(f"No hi ha ContractConsumption per al mes {month}"))
        
        # Mostrar readings anteriors
        from billing.models import Reading
        last_readings = Reading.objects.filter(
            supply_point=supply_point,
            contract=contract,
            reading_value__isnull=False
        ).order_by('-reading_date')[:5]
        
        if last_readings.exists():
            self.stdout.write(f"\nÚltimes 5 readings per a aquest supply point i contracte:")
            for reading in last_readings:
                self.stdout.write(
                    f"  ID: {reading.id}, Data: {reading.reading_date}, "
                    f"Valor: {reading.reading_value}, "
                    f"Calculat: {reading.calculated_value}, "
                    f"Estimada: {reading.is_estimated}"
                )
        else:
            self.stdout.write(self.style.WARNING(f"No hi ha readings anteriors per a aquest supply point i contracte"))
        
        # Executar la funció
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("Executant get_estimated_reading_minimal_object...")
        self.stdout.write(f"{'='*60}\n")
        
        try:
            reading = get_estimated_reading_minimal_object(supply_point, contract, target_date, batch)
            
            # Mostrar el resultat
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write("RESULTAT:")
            self.stdout.write(f"{'='*60}")
            self.stdout.write(self.style.SUCCESS(f"✅ Reading creat/actualitzat amb èxit"))
            self.stdout.write(f"\nDetalls del Reading:")
            self.stdout.write(f"  ID: {reading.id}")
            self.stdout.write(f"  Token: {reading.token}")
            self.stdout.write(f"  Data: {reading.reading_date}")
            self.stdout.write(f"  Valor lectura: {reading.reading_value}")
            self.stdout.write(f"  Valor calculat: {reading.calculated_value}")
            self.stdout.write(f"  Dies de consum: {reading.consumption_days}")
            self.stdout.write(f"  És estimada: {reading.is_estimated}")
            self.stdout.write(f"  Origen: {reading.origin}")
            if reading.previous_reading:
                self.stdout.write(f"  Reading anterior ID: {reading.previous_reading.id}")
            if reading.batch:
                self.stdout.write(f"  Batch ID: {reading.batch.id}")
            self.stdout.write(f"{'='*60}\n")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Error en executar la funció:"))
            self.stdout.write(self.style.ERROR(f"{type(e).__name__}: {str(e)}"))
            import traceback
            self.stdout.write("\nTraceback:")
            self.stdout.write(traceback.format_exc())
            raise CommandError(f"Error en executar la funció: {e}")

