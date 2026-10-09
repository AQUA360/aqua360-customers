from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from coredata.models import Street, StreetNumber, StreetNumberType, StreetType
# from .serializers import (
#   ChildModelASerializer,
#   ChildModelBSerializer,
#   ChildModelCSerializer,
#   ChildModelDSerializer,
# )
from coredata.permissions import AddressPermission
class PartialAddressViewSet(APIView):
  permission_classes = [IsAuthenticated, AddressPermission]
  queryset = Street.objects.all().order_by('-created_at')
  def post(self, request, *args, **kwargs):
    # Extract data for each child model from the request
    
    print(request.data)
    
    street_data = request.data.get('address_street', {})
    street_number_data = request.data.get('address_street_number', {})

    street = None
    street_number = None

    if street_data:
      type_abbreviation = street_data.pop('type_abbreviation', None)
      type_name = street_data.pop('type_name', '')

      # Usem filter().first() per evitar MultipleObjectsReturned si hi ha duplicats
      street_type = StreetType.objects.filter(abbreviation=type_abbreviation).first()
      if not street_type:
          street_type = StreetType.objects.create(
              abbreviation=type_abbreviation,
              name=type_name or type_abbreviation
          )

      from coredata.models import City
      city_id = request.data.get('address_city')
      city = City.objects.filter(id=city_id).first() if city_id else None

      # Cerquem o creem el carrer. Mai no modifiquem un que ja existeixi.
      # Normalitzem per evitar duplicats per espais o NULL vs ''
      street_name = street_data.get('name', '').strip()
      street_name_2 = street_data.get('name_2') or ''

      street = Street.objects.filter(
        type=street_type,
        name=street_name,
        name_2=street_name_2,
        city=city
      ).first()

      if not street:
          street = Street.objects.create(
            type=street_type,
            name=street_name,
            name_2=street_name_2,
            city=city
          )

    if street_number_data and street:
      street_number_type_data = street_number_data.pop('number_type', {})
      number_type_type_data = street_number_type_data.pop('type', None)

      if number_type_type_data:
        street_number_type = StreetNumberType.objects.filter(
          type=number_type_type_data
        ).first()

        if street_number_type:
            # Cerquem o creem el número de carrer lligat al carrer. Mai no modifiquem un que ja existeixi.
            number = street_number_data.get('number', None)
            number_end = street_number_data.get('number_end', None)
            number_suffix = street_number_data.get('number_suffix') or ''
            number_end_suffix = street_number_data.get('number_end_suffix') or ''

            street_number = StreetNumber.objects.filter(
              street=street,
              number_type=street_number_type,
              number=number,
              number_end=number_end,
              number_suffix=number_suffix,
              number_end_suffix=number_end_suffix
            ).first()

            if not street_number:
              street_number = StreetNumber.objects.create(
                street=street,
                number_type=street_number_type,
                number=number,
                number_end=number_end,
                number_suffix=number_suffix,
                number_end_suffix=number_end_suffix
              )

    response = {
      'street': street.id if street else None,
      'street_number': street_number.id if street_number else None
    }
    return Response(response, status=status.HTTP_201_CREATED)

    # Validate and create ChildModelA instance
    # serializer_a = ChildModelASerializer(data=street_data)
    # if serializer_a.is_valid():
    #     serializer_a.save()
    # data_c = request.data.get('child_c', {})
    # data_d = request.data.get('child_d', {})

    # # Create a list to hold any errors
    # errors = {}

    # # Validate and create ChildModelA instance
    # serializer_a = ChildModelASerializer(data=data_a)
    # if serializer_a.is_valid():
    #     serializer_a.save()
    # else:
    #     errors['child_a'] = serializer_a.errors

    # # Validate and create ChildModelB instance
    # serializer_b = ChildModelBSerializer(data=data_b)
    # if serializer_b.is_valid():
    #     serializer_b.save()
    # else:
    #     errors['child_b'] = serializer_b.errors

    # # Validate and create ChildModelC instance
    # serializer_c = ChildModelCSerializer(data=data_c)
    # if serializer_c.is_valid():
    #     serializer_c.save()
    # else:
    #     errors['child_c'] = serializer_c.errors

    # # Validate and create ChildModelD instance
    # serializer_d = ChildModelDSerializer(data=data_d)
    # if serializer_d.is_valid():
    #     serializer_d.save()
    # else:
    #     errors['child_d'] = serializer_d.errors

    # # If there are any errors, return them in the response
    # if errors:
    #     return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    return Response({"message": "All objects created successfully"}, status=status.HTTP_201_CREATED)