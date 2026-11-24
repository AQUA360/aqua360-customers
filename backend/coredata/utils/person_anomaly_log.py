"""Historial de les anomalies de la persona (PersonLog)."""
import uuid

from coredata.models import PersonLog


def describe_anomaly(anomaly):
    end = f" - {anomaly.end_date.isoformat()}" if anomaly.end_date else ''
    observation = f": {anomaly.observation}" if anomaly.observation else ''
    return f"{anomaly.anomaly_type.name} ({anomaly.start_date.isoformat()}{end}){observation}"


def log_anomaly_change(anomaly, user, old_value, new_value):
    """Deixa l'alta, la modificació o la baixa de l'anomalia a l'historial de canvis de la persona."""
    PersonLog.objects.create(
        person=anomaly.person,
        field_name='anomaly',
        old_value=old_value,
        new_value=new_value,
        operation_token=str(uuid.uuid4()),
        user=user,
    )
