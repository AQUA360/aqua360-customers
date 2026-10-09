import logging
from decimal import Decimal, ROUND_HALF_UP
from django.core.management.base import BaseCommand
from django.db import transaction
from billing.models import Reading, ReadingBatch, EstimatedBag, EstimatedBagMovement
from billing.utils.reading_service import get_statistical_daily_avg, recalc_calc_value_gen_meter
from coredata.models import ConfigProject

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Recalculate calculated_value for all ESTIMATED readings in a specific ReadingBatch based on current statistics'

    def add_arguments(self, parser):
        parser.add_argument('batch_token', type=str, help='Token or ID of the ReadingBatch')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without saving',
        )

    def handle(self, *args, **options):
        batch_token = options['batch_token']
        dry_run = options['dry_run']

        try:
            batch = ReadingBatch.objects.get(token=batch_token)
        except ReadingBatch.DoesNotExist:
            try:
                batch = ReadingBatch.objects.get(id=batch_token)
            except (ReadingBatch.DoesNotExist, ValueError):
                self.stderr.write(self.style.ERROR(f"ReadingBatch '{batch_token}' not found."))
                return

        # Nota: no filtrem per `origin` (text lliure i traduïble segons l'idioma actiu
        # en el moment de crear la lectura). `is_estimated=True` ja identifica de forma
        # fiable les lectures estimades independentment del format/idioma de l'origen.
        readings = Reading.objects.filter(
            batch=batch,
            is_estimated=True,
            calculated_value=0,
            is_active=True
        ).select_related('contract', 'supply_point', 'supply_point__meter', 'supply_point__meter__status')
        
        total = readings.count()
        if total == 0:
            self.stdout.write(f"No active estimated readings found in batch {batch.token}.")
            return

        self.stdout.write(f"Processing {total} estimated readings in batch {batch.token}...")
        
        updated_count = 0
        
        # Load minimum consumption fallback
        min_consumption = ConfigProject.objects.filter(token='minimum_consumption').first()
        monthly_min = Decimal(str(min_consumption.value)) if min_consumption and min_consumption.value else Decimal('6')
        fallback_daily_avg = monthly_min / Decimal('30.44')

        for reading in readings:
            contract = reading.contract
            if not contract:
                self.stdout.write(self.style.WARNING(f"Skipping Reading {reading.id}: No contract associated."))
                continue

            # 1. Get current daily average from statistics (this will use the fix I just applied)
            daily_avg = get_statistical_daily_avg(
                contract, 
                reading.reading_date.month, 
                target_year=reading.reading_date.year, 
                offset_days=reading.consumption_days
            )
            
            if daily_avg is None:
                daily_avg = fallback_daily_avg
            
            if daily_avg < 0:
                daily_avg = Decimal('0')

            # 2. Calculate new estimate
            days = reading.consumption_days or 0
            new_calculated_value = (daily_avg * Decimal(str(days))).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            
            # Apply general meter logic if applicable
            new_calculated_value = float(recalc_calc_value_gen_meter(reading, new_calculated_value, reading.supply_point))

            old_calculated_value = float(reading.calculated_value or 0)
            
            if abs(old_calculated_value - new_calculated_value) > 0.001:
                self.stdout.write(
                    f"Reading {reading.id} (Contract {contract.token}): "
                    f"{old_calculated_value} -> {new_calculated_value} "
                    f"({daily_avg:.4f} m3/day over {days} days)"
                )
                
                if not dry_run:
                    with transaction.atomic():
                        diff = new_calculated_value - old_calculated_value
                        
                        # Update reading
                        reading.calculated_value = new_calculated_value
                        # real_consumption fallback logic
                        estimated_used = float(reading.estimated_used or 0)
                        reading.real_consumption = new_calculated_value - estimated_used
                        reading.save(update_fields=['calculated_value', 'real_consumption'])
                        
                        # Update EstimatedBag if exists
                        try:
                            bag = EstimatedBag.objects.get(supply_point=reading.supply_point, contract=contract)
                            bag.total_consumption = float(bag.total_consumption) + diff
                            bag.save(update_fields=['total_consumption'])
                            
                            # Update corresponding movement
                            movement = EstimatedBagMovement.objects.filter(reading=reading).first()
                            if movement:
                                movement.amount = new_calculated_value
                                movement.save(update_fields=['amount'])
                        except EstimatedBag.DoesNotExist:
                            pass
                    
                    updated_count += 1
            
        if dry_run:
            self.stdout.write(self.style.WARNING(f"\nDry-run finished. Would have updated {updated_count} readings."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nSuccessfully updated {updated_count} readings in batch {batch.token}."))
