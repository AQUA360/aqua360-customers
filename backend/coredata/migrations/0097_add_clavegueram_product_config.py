from django.db import migrations

def create_clavegueram_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    Product = apps.get_model('pricing', 'Product')
    
    # Intentar buscar el producte "CLAVEGUERAM" de forma intel·ligent per pouar-ne el seu token dinàmicament
    default_value = 'CLV'
    try:
        product = Product.objects.filter(name__icontains='CLAVEGUERAM').first()
        if product and product.token:
            default_value = product.token
    except Exception:
        pass
        
    ConfigProject.objects.get_or_create(
        token='report_clavegueram_product_token',
        defaults={
            'name': 'Exportació Clavegueram - Product Token',
            'value': default_value
        }
    )

def reverse_clavegueram_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token='report_clavegueram_product_token').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0096_add_no_address_number_type_config'),
    ]

    operations = [
        migrations.RunPython(create_clavegueram_config, reverse_clavegueram_config),
    ]
