from rest_framework import views, viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django.db import transaction
from datetime import datetime
import pandas as pd
from billing.models import Reading
# from ..utils.aca_document_service import process_document

class ReadingsViewSet(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Reading.objects.all().order_by('-created_at')
    def post(self, request):
        try:
            file = request.data.get('file')
            
            changes_data = process_file(file)
            
            return Response("OK", status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": f"Unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def process_file(file):
    try:
        with transaction.atomic():
            print("HERE")

            # Initialize df as None to ensure it is defined in all cases
            df = None
            results = []

            try:
                # Check if the file is actually HTML content
                file_start = file.read(1024).decode(errors='ignore').lower()
                file.seek(0)  # Reset file pointer after reading

                if file_start.startswith('<html') or file_start.startswith('<table'):
                    # Parse as HTML table
                    df = pd.read_html(file, header=0)[0]  # reads the first table found

                    # Collect data for each row
                    for index, row in df.iterrows():
                        abonat = row['ABONAT']
                        numdoc = row['NUMDOC']
                        adreca = row['ADREÇA']
                        codpos = row['CODPOS']
                        municipi = row['MUNICIPI']
                        numpol = row['NUMPOL']

                        # Append each row as a dictionary to results
                        results.append({
                        'person_name': abonat,
                        'person_NIF': numdoc,
                        'address': adreca,
                        'postal_code': codpos,
                        'city_code': municipi,
                        'contract_code': numpol
                        })
                        print(f"Processed data for {abonat}")

                else:
                    raise ValueError("Unsupported file format. Expected an HTML table.")

            except Exception as e:
                print("Error reading or processing the file.")
                raise
            
            if df is not None:
                return results  # Return processed data as list of dictionaries

            else:
                raise ValueError("DataFrame is None. File parsing may have failed.")

    except Exception as e:
        print("An error occurred while processing the document.")
        raise