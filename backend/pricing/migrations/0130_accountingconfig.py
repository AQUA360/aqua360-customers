import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pricing', '0129_accountingpricing_payment_origin_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccountingConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True, blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True, null=True, blank=True)),
                ('piggybank_as_negative', models.BooleanField(default=False)),
                ('include_piggy_status_payments', models.BooleanField(default=False)),
                ('incoming_declare_as', models.CharField(
                    choices=[('debt', 'Debt'), ('have', 'Have')],
                    default='debt',
                    max_length=10,
                )),
                ('incoming_sign', models.CharField(
                    choices=[('positive', 'Positive'), ('negative', 'Negative')],
                    default='positive',
                    max_length=10,
                )),
                ('incoming_counter_declare_as', models.CharField(
                    choices=[('debt', 'Debt'), ('have', 'Have'), ('none', 'Not declared')],
                    default='have',
                    max_length=10,
                )),
                ('return_declare_as', models.CharField(
                    choices=[('debt', 'Debt'), ('have', 'Have')],
                    default='have',
                    max_length=10,
                )),
                ('return_sign', models.CharField(
                    choices=[('positive', 'Positive'), ('negative', 'Negative')],
                    default='positive',
                    max_length=10,
                )),
                ('return_counter_declare_as', models.CharField(
                    choices=[('debt', 'Debt'), ('have', 'Have'), ('none', 'Not declared')],
                    default='debt',
                    max_length=10,
                )),
                ('is_active', models.BooleanField(default=True)),
                ('incoming_counter_pricing', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='incoming_piggybank_configs',
                    to='pricing.accountingpricing',
                )),
                ('return_counter_pricing', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='return_piggybank_configs',
                    to='pricing.accountingpricing',
                )),
            ],
            options={
                'verbose_name': 'Accounting config',
                'verbose_name_plural': 'Accounting configs',
            },
        ),
    ]
