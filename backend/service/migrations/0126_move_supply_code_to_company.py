from django.db import migrations, models


# El codi d'entitat subministradora de l'ACA identifica l'empresa que declara (la mateixa
# de la qual s'agafa el NIF), no l'explotació. Es mou de Exploitation a Company sense
# perdre cap valor: cada explotació el passa a la seva empresa (FK `company` i M2M
# `companies`) i, si l'empresa principal (ConfigProject 'main_company_token') no el té,
# també a aquesta. Mai se sobreescriu un valor que l'empresa ja tingui.


def copy_supply_code_to_company(apps, schema_editor):
    Exploitation = apps.get_model('service', 'Exploitation')
    Company = apps.get_model('service', 'Company')
    ConfigProject = apps.get_model('coredata', 'ConfigProject')

    # Primer les actives: si dues explotacions de la mateixa empresa tenen codis
    # diferents, mana la de l'activa (la que ja feien servir els exports ACA).
    exploitations = (
        Exploitation.objects
        .exclude(supply_code__isnull=True)
        .exclude(supply_code='')
        .order_by('-is_active', 'id')
    )

    supply_codes = {}
    for exploitation in exploitations:
        company_ids = set(exploitation.companies.values_list('id', flat=True))
        if exploitation.company_id:
            company_ids.add(exploitation.company_id)
        for company_id in company_ids:
            current = supply_codes.setdefault(company_id, exploitation.supply_code)
            if current != exploitation.supply_code:
                print(
                    f"\n  [supply_code] Company {company_id}: es manté '{current}' i es descarta "
                    f"'{exploitation.supply_code}' de l'Exploitation {exploitation.id}"
                )

    main_company_vat = ConfigProject.objects.filter(token='main_company_token').values_list('value', flat=True).first()
    main_company = Company.objects.filter(vat=main_company_vat).first() if main_company_vat else None
    first_supply_code = exploitations.values_list('supply_code', flat=True).first()
    if main_company and first_supply_code:
        supply_codes.setdefault(main_company.id, first_supply_code)

    for company in Company.objects.filter(id__in=supply_codes):
        if company.supply_code:
            continue
        company.supply_code = supply_codes[company.id]
        company.save(update_fields=['supply_code'])


def copy_supply_code_to_exploitation(apps, schema_editor):
    Exploitation = apps.get_model('service', 'Exploitation')

    for exploitation in Exploitation.objects.select_related('company').filter(company__supply_code__isnull=False):
        exploitation.supply_code = exploitation.company.supply_code
        exploitation.save(update_fields=['supply_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0125_giswater_mincut_explicit_maps'),
        ('coredata', '0089_configproject_value_bool'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='supply_code',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.RunPython(copy_supply_code_to_company, copy_supply_code_to_exploitation),
        migrations.RemoveField(
            model_name='exploitation',
            name='supply_code',
        ),
    ]
