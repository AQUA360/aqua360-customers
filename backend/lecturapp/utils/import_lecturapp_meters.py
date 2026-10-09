#!/usr/bin/env python
"""
Script to import readings from a CSV file.
Processes each row similar to the sync_readings function in lecturapp/views.py

Usage:
    python manage.py shell < lecturapp/utils/import_lecturapp_meters.py
    OR
    python lecturapp/utils/import_lecturapp_meters.py (if Django is set up)

Dry run (report would-create / would-update counts without writing):
    python lecturapp/utils/import_lecturapp_meters.py --dry-run
    python lecturapp/utils/import_lecturapp_meters.py -n
"""

import os
import sys
import django
from datetime import datetime
import base64

# Setup Django environment
if __name__ == '__main__':
    # Find the project root by looking for manage.py
    script_path = os.path.abspath(__file__)
    current_dir = os.path.dirname(script_path)
    
    # Go up directories until we find manage.py
    project_dir = current_dir
    while project_dir != os.path.dirname(project_dir):  # Stop at root
        if os.path.exists(os.path.join(project_dir, 'manage.py')):
            break
        project_dir = os.path.dirname(project_dir)
    
    if not os.path.exists(os.path.join(project_dir, 'manage.py')):
        print("Error: Could not find project root (manage.py). Please run from project directory.")
        sys.exit(1)
    
    # Add the project directory to the Python path
    sys.path.insert(0, project_dir)
    
    # Set the Django settings module
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customers.settings')
    django.setup()

# Import Django models and utilities after django.setup()
import csv
from django.core.files.base import ContentFile
from billing.models import ReaderAlert, ReadingBatch, Reading
from contract.models import Contract
from service.models import Meter, SupplyPoint, SupplyPointPlacement
from lecturapp.models import ReadingOperator


def process_reading_row(row_data, reading_batch, operator, dry_run=False):
    """
    Process a single row of reading data, similar to sync_readings function.

    Args:
        row_data: Dictionary with reading data (keys should match expected fields)
        reading_batch: ReadingBatch instance
        operator: ReadingOperator instance
        dry_run: If True, validate and report what would be done but do not write to DB.

    Returns:
        (meter_id, action) if successful: action is 'created' or 'updated'.
        (None, None) on validation failure or error.
    """
    print(f"-----------------------------------------")
    
    # Get meter by ID or code
    meter_code = row_data.get('meter_code') or row_data.get('code')
    
    if not meter_code:
        print(f"Skipping reading - no meter code provided")
        return (None, None)

    try:
        meter = Meter.objects.get(code=meter_code)
    except Meter.DoesNotExist:
        print(f"Meter with code {meter_code} not found")
        return (None, None)
    
    print(f"Reading Meter: {meter.id} - {meter.code}")
    
    # Get fields to update (comma-separated string or list)
    fields_to_update_str = row_data.get('changes_to_save', '')
    if isinstance(fields_to_update_str, str):
        fields_to_update = [f.strip() for f in fields_to_update_str.split(',') if f.strip()]
    else:
        fields_to_update = fields_to_update_str if fields_to_update_str else []
    
    print(f"Fields to update: {fields_to_update}")
    
    # Get previous reading if provided
    previous_reading = None
    if row_data.get('previous_reading_id'):
        try:
            previous_reading = Reading.objects.get(id=row_data.get('previous_reading_id'))
        except Reading.DoesNotExist:
            print(f"Previous reading with ID {row_data.get('previous_reading_id')} not found")

    # Check if reading already exists for this meter in this batch
    existing_reading = Reading.objects.filter(
        batch=reading_batch,
        meter=meter
    ).first()
    
    # Calculate consumption value safely
    new_reading_value = row_data.get('new_reading')
    previous_reading_value = row_data.get('last_reading')
    
    # Handle None values for calculation
    if new_reading_value is None:
        new_reading_value = 0
    if previous_reading_value is None:
        previous_reading_value = 0
    
    # Convert to float if string
    try:
        new_reading_value = float(new_reading_value) if new_reading_value else 0
        previous_reading_value = float(previous_reading_value) if previous_reading_value else 0
    except (ValueError, TypeError):
        new_reading_value = 0
        previous_reading_value = 0
    
    calculated_value = new_reading_value - previous_reading_value if new_reading_value != 0 else 0
    
    reading_data = {
        'batch': reading_batch,
        'meter': meter,
        'operator': operator,
        'previous_reading': previous_reading,
        'calculated_value': calculated_value,
        'origin': 'lecturapp'
    }
    
    # Handle reading date
    if 'new_reading_date' in fields_to_update or row_data.get('new_reading_date'):
        reading_date_str = row_data.get('new_reading_date') or row_data.get('reading_date')
        if reading_date_str:
            try:
                # Handle datetime objects
                if isinstance(reading_date_str, datetime):
                    reading_date = reading_date_str.date()
                elif isinstance(reading_date_str, str):
                    # Handle ISO 8601 datetime format (2025-07-29T08:37:08.647Z)
                    if 'T' in reading_date_str:
                        reading_datetime = datetime.fromisoformat(reading_date_str.replace('Z', '+00:00'))
                        reading_date = reading_datetime.date()
                    else:
                        # Handle simple date format YYYY-MM-DD
                        reading_date = datetime.strptime(reading_date_str, '%Y-%m-%d').date()
                else:
                    reading_date = datetime.now().date()
                reading_data['reading_date'] = reading_date
            except (ValueError, AttributeError) as e:
                print(f"Invalid date format: {reading_date_str} - {e}")
                reading_data['reading_date'] = datetime.now().date()
        else:
            reading_data['reading_date'] = datetime.now().date()
    
    # Handle reading value
    if 'new_reading' in fields_to_update or row_data.get('new_reading') or row_data.get('reading_value'):
        reading_value = row_data.get('new_reading') or row_data.get('reading_value')
        if reading_value is not None:
            try:
                reading_data['reading_value'] = float(reading_value)
            except (ValueError, TypeError):
                print(f"Invalid reading value: {reading_value}")
                # Don't continue, just skip this field
    
    # Handle reader alert
    if 'reader_alert' in fields_to_update or row_data.get('reader_alert'):
        reader_alert_data = row_data.get('reader_alert')
        if isinstance(reader_alert_data, str):
            reader_alert_name = reader_alert_data
        elif isinstance(reader_alert_data, dict):
            reader_alert_name = reader_alert_data.get('name')
        else:
            reader_alert_name = None
        
        if reader_alert_name:
            if dry_run:
                reader_alert = ReaderAlert.objects.filter(name=reader_alert_name).first()
            else:
                reader_alert, _ = ReaderAlert.objects.get_or_create(
                    name=reader_alert_name,
                    defaults={'token': reader_alert_name}
                )
            reading_data['reader_alert'] = reader_alert
    
    # Handle photo (base64 encoded or file path)
    if 'new_photo' in fields_to_update or row_data.get('new_photo'):
        photo_data = row_data.get('new_photo')
        if photo_data:
            try:
                # If it's a file path, read the file
                if isinstance(photo_data, str) and os.path.exists(photo_data):
                    with open(photo_data, 'rb') as f:
                        image_data = f.read()
                # If it's base64 encoded
                elif isinstance(photo_data, str):
                    # Strip whitespace and newlines
                    photo_data = photo_data.strip()
                    
                    # Skip if empty after stripping
                    if not photo_data:
                        print(f"Warning: Empty photo data for meter {meter.id}")
                        reading_data['photo'] = None
                    else:
                        # Decode base64 image data
                        if photo_data.startswith('data:image'):
                            # Remove data URL prefix
                            photo_data = photo_data.split(',')[1].strip()
                        
                        # Validate and fix base64 string
                        # Base64 strings should have length that is a multiple of 4
                        # Add padding if needed
                        missing_padding = len(photo_data) % 4
                        if missing_padding:
                            photo_data += '=' * (4 - missing_padding)
                        
                        # Validate base64 characters (optional but helpful)
                        try:
                            # Try to decode to validate
                            image_data = base64.b64decode(photo_data, validate=True)
                        except Exception as decode_error:
                            # If validation fails, try without validation (more lenient)
                            print(f"Warning: Base64 validation failed for meter {meter.id}, attempting lenient decode: {decode_error}")
                            try:
                                image_data = base64.b64decode(photo_data, validate=False)
                            except Exception as e:
                                print(f"Error: Cannot decode base64 photo data for meter {meter.id}: {e}")
                                print(f"  Base64 string length: {len(photo_data)}, first 50 chars: {photo_data[:50]}")
                                reading_data['photo'] = None
                                image_data = None
                else:
                    image_data = None
                
                if image_data:
                    image_file = ContentFile(
                        image_data, 
                        name=f"reading_{meter.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    )
                    reading_data['photo'] = image_file
                elif 'photo' not in reading_data:
                    reading_data['photo'] = None
            except Exception as e:
                print(f"Error processing photo for meter {meter.id}: {e}")
                reading_data['photo'] = None
        else:
            reading_data['photo'] = None
    
    # Handle cluster nozzle
    if not dry_run and ('cluster_nozzle_col' in fields_to_update or 'cluster_nozzle_row' in fields_to_update):
        supply_point = SupplyPoint.objects.filter(meter=meter).first()
        if supply_point and supply_point.cluster_nozzle:
            cluster_nozzle = supply_point.cluster_nozzle
            if 'cluster_nozzle_col' in fields_to_update or row_data.get('cluster_nozzle_col'):
                cluster_nozzle.col = row_data.get('cluster_nozzle_col')
            if 'cluster_nozzle_row' in fields_to_update or row_data.get('cluster_nozzle_row'):
                cluster_nozzle.row = row_data.get('cluster_nozzle_row')
            cluster_nozzle.save()

    # Handle supply placement
    if not dry_run and ('supply_placement' in fields_to_update or row_data.get('supply_placement_id')):
        supply_placement_id = row_data.get('supply_placement_id')
        if supply_placement_id:
            try:
                supply_placement = SupplyPointPlacement.objects.get(id=supply_placement_id)
                supply_point = SupplyPoint.objects.filter(meter=meter).first()
                if supply_point:
                    supply_point.placement = supply_placement
                    supply_point.save()
            except SupplyPointPlacement.DoesNotExist:
                print(f"SupplyPointPlacement with ID {supply_placement_id} not found")

    # Create or update reading
    if existing_reading:
        if not dry_run:
            for field, value in reading_data.items():
                if field != 'photo':  # Handle photo separately
                    setattr(existing_reading, field, value)
            if 'photo' in reading_data:
                existing_reading.photo = reading_data['photo']
            existing_reading.save()
        print(f"{'[DRY-RUN] Would update' if dry_run else 'Updated'} reading for meter {meter.id}")
        return (meter.id, 'updated')
    else:
        # Only create if we have required fields
        if 'new_reading_date' in fields_to_update or row_data.get('new_reading_date') or row_data.get('reading_date'):
            supply_token = row_data.get('supply_token')
            contract_token = row_data.get('contract_token')

            if supply_token and contract_token:
                try:
                    supply_point = SupplyPoint.objects.get(token=supply_token)
                    contract = Contract.objects.get(token=contract_token)
                    if not dry_run:
                        reading_data['contract'] = contract
                        reading_data['token'] = f"{meter.code}/{reading_batch.token}"
                        reading_data['supply_point'] = supply_point
                        Reading.objects.create(**reading_data)
                    print(f"{'[DRY-RUN] Would create' if dry_run else 'Created'} new reading for meter {meter.id}")
                    return (meter.id, 'created')
                except (SupplyPoint.DoesNotExist, Contract.DoesNotExist) as e:
                    print(f"Error creating reading: {e}")
                    return (None, None)
            else:
                print(f"Skipping reading creation - missing supply_token or contract_token")
                return (None, None)
        else:
            # No date field to create from - treat as would-update path doesn't apply; row is invalid for create
            return (None, None)


def read_csv_file(file_path):
    """
    Read a CSV file and return a list of dictionaries, one per row.
    First row should contain headers.
    """
    try:
        # Increase CSV field size limit to handle large fields (e.g., base64 encoded images)
        # Default limit is 131072 (128KB), we'll increase it significantly
        max_int = sys.maxsize
        while True:
            try:
                csv.field_size_limit(max_int)
                break
            except OverflowError:
                max_int = int(max_int / 10)
        
        rows_data = []
        with open(file_path, 'r', encoding='utf-8-sig') as csvfile:
            # Use DictReader to automatically use first row as headers
            reader = csv.DictReader(csvfile, delimiter=',')
            for row in reader:
                # Convert empty strings to None for consistency
                row_dict = {k: (v if v else None) for k, v in row.items()}
                rows_data.append(row_dict)
        return rows_data
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return None


def main():
    """Main function to run the import script"""
    # Ask for reading batch ID
    reading_batch_id = input("Enter Reading Batch ID: ").strip()
    if not reading_batch_id:
        print("Error: Reading Batch ID is required")
        return
    
    try:
        reading_batch_id = int(reading_batch_id)
    except ValueError:
        print("Error: Reading Batch ID must be a number")
        return
    
    try:
        reading_batch = ReadingBatch.objects.get(id=reading_batch_id)
    except ReadingBatch.DoesNotExist:
        print(f"Error: Reading Batch with ID {reading_batch_id} not found")
        return
    
    print(f"Reading batch: {reading_batch}")
    
    # Ask for CSV file path
    file_path = input("Enter path to CSV file: ").strip()
    if not file_path:
        print("Error: File path is required")
        return
    
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return
    
    # Get operator (use first active operator or ask)
    operator = ReadingOperator.objects.filter(is_active=True).first()
    if not operator:
        print("Error: No active operator found. Please create one first.")
        return
    
    print(f"Using operator: {operator}")
    
    # Read CSV file
    print(f"\nReading CSV file: {file_path}")
    rows_data = read_csv_file(file_path)
    
    if not rows_data:
        print("Error: No data found in CSV file or error reading file")
        return
    
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    if dry_run:
        print("\n*** DRY RUN - no changes will be written ***\n")

    print(f"Found {len(rows_data)} rows to process\n")

    # Process each row
    meter_ids = []
    processed_count = 0
    error_count = 0
    would_create = 0
    would_update = 0

    for i, row_data in enumerate(rows_data, 1):
        try:
            row_batch_id = int(row_data.get('reading_batch_id')) if row_data.get('reading_batch_id') else None
        except (TypeError, ValueError):
            row_batch_id = None
        changes_to_save = row_data.get('changes_to_save') or ''
        if changes_to_save != '' and row_batch_id == reading_batch_id:
            try:
                result = process_reading_row(row_data, reading_batch, operator, dry_run=dry_run)
                meter_id, action = result if result else (None, None)
                if meter_id:
                    if dry_run:
                        if action == 'created':
                            would_create += 1
                        elif action == 'updated':
                            would_update += 1
                    else:
                        meter_ids.append(meter_id)
                        processed_count += 1
                else:
                    error_count += 1
            except Exception as e:
                print(f"Error processing row {i}: {e}")
                error_count += 1

    # Print summary
    print(f"\n{'='*50}")
    print(f"Import Summary{' (DRY RUN)' if dry_run else ''}:")
    print(f"  Total rows: {len(rows_data)}")
    if dry_run:
        print(f"  Would create: {would_create}")
        print(f"  Would update: {would_update}")
        print(f"  Errors / skipped: {error_count}")
    else:
        print(f"  Successfully processed: {processed_count}")
        print(f"  Errors: {error_count}")
    print(f"  Batch ID: {reading_batch_id}")
    print(f"  Operator ID: {operator.id if operator else None}")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()

