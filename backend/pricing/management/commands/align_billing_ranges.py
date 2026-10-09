import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from pricing.models import PriceRate, BillingRange

from django.db.models import Q

class Command(BaseCommand):
    help = "Aligns BillingRange end dates to match the start date of the subsequent BillingRange."

    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
            help='Commit changes to the database (defaults to dry-run)',
        )

    def handle(self, *args, **options):
        commit = options.get('commit')
        if not commit:
            self.stdout.write(self.style.WARNING("DRY RUN: No changes will be committed. Use --commit to apply changes."))

        # Filter price rates corresponding to CANON AIGUA (ACA) or similar products, omitting inactive ones
        price_rates = PriceRate.objects.filter(
            Q(product__name__icontains="CÀNON AIGUA (ACA)") | Q(product__name__icontains="CANON AIGUA (ACA)"),
            is_active=True
        )
        total_updated = 0

        with transaction.atomic():
            for pr in price_rates:
                # Get all billing ranges for this PriceRate sorted by start date
                ranges = list(BillingRange.objects.filter(price_rate=pr).order_by('start', 'id'))
                if not ranges:
                    continue

                # Determine the current active range
                current_range = pr.billing_range_active
                if not current_range:
                    current_range = ranges[-1]

                # Find the index of the current active range in the sorted list
                try:
                    current_idx = ranges.index(current_range)
                except ValueError:
                    current_range = ranges[-1]
                    current_idx = len(ranges) - 1

                # Only modify the end date of the range prior to the current one, if it exists
                if current_idx > 0:
                    prev_range = ranges[current_idx - 1]

                    if prev_range.is_active and prev_range.end != current_range.start:
                        self.stdout.write(
                            f"PriceRate: {pr.name} (id: {pr.id}) | BillingRange ID {prev_range.id} (start: {prev_range.start}, end: {prev_range.end}) "
                            f"-> Updating end to match next start: {current_range.start}"
                        )
                        if commit:
                            prev_range.end = current_range.start
                            prev_range.save()
                        total_updated += 1

        if commit:
            self.stdout.write(self.style.SUCCESS(f"Successfully updated {total_updated} billing range end dates."))
        else:
            self.stdout.write(self.style.WARNING(f"[DRY RUN] Would update {total_updated} billing range end dates."))
