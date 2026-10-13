from django.db import migrations


def copy_routings_to_transfer(apps, schema_editor):
    """
    Fins ara el mateix mapa servia per a remeses i per a transferències de
    retorn. Es duplica cada fila com a `transfer` perquè els retorns segueixin
    sortint pel mateix compte que abans fins que algú en canviï el mapa.
    """
    CompanyBankRouting = apps.get_model('service', 'CompanyBankRouting')
    CompanyBankRouting.objects.bulk_create([
        CompanyBankRouting(
            company_id=routing.company_id,
            company_bank_id=routing.company_bank_id,
            bank_id=routing.bank_id,
            match_type=routing.match_type,
            is_active=routing.is_active,
            operation='transfer',
        )
        for routing in CompanyBankRouting.objects.filter(operation='collection')
    ])


def delete_transfer_routings(apps, schema_editor):
    CompanyBankRouting = apps.get_model('service', 'CompanyBankRouting')
    CompanyBankRouting.objects.filter(operation='transfer').delete()


class Migration(migrations.Migration):
    """
    Va a part de la 0131: a Postgres no es pot crear l'índex de les
    restriccions úniques a la mateixa transacció on s'han inserit les files.
    """

    dependencies = [
        ('service', '0131_companybankrouting_operation'),
    ]

    operations = [
        migrations.RunPython(copy_routings_to_transfer, delete_transfer_routings),
    ]
