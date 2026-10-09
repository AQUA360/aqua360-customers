from coredata.models import ConfigProject

SHOW_ALL_CONSUMPTION_TRAMS_TOKEN = 'SHOW_ALL_CONSUMPTION_TRAMS'


def should_show_all_consumption_trams():
    """
    Retorna si cal mostrar a la factura tots els trams de consum de la tarifa,
    inclosos els que no tenen consum en el període facturat, segons el valor
    del ConfigProject amb token `SHOW_ALL_CONSUMPTION_TRAMS`.
    """
    config = ConfigProject.objects.filter(token=SHOW_ALL_CONSUMPTION_TRAMS_TOKEN).first()
    if not config or not config.value:
        return False
    return config.value.lower() == 'true'
