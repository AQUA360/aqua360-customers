from django.db import migrations
 
def add_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token='order_status_draft_token').exists():
        ConfigProject.objects.create(
            token='order_status_draft_token',
            name='Token de OrderStatus de Draft',
            value='0'
        )
 
 
class Migration(migrations.Migration):
 
    dependencies = [
        ('order', '0033_order_created_by'),
    ]
 
    operations = [
        migrations.RunPython(add_config),
    ]
 