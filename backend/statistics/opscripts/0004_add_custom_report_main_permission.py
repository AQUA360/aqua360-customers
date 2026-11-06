"""Registra el permís principal dels informes personalitzats (explorer.Query).

`view_custom_report` -> veure i executar informes desats; `change_custom_report` -> crear-los,
editar-los i executar SQL lliure. No modifica el registre si ja existeix.
"""


def run():
    from coredata.models import MainPermission

    MainPermission.objects.get_or_create(
        name='custom_report',
        defaults={
            'view_key': 'view_custom_report',
            'change_key': 'change_custom_report',
            'affected_models': 'explorer.query',
            'is_default': False,
        },
    )
