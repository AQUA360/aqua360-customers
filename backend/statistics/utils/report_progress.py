def report_progress(task, current, total, every=50):
    """
    Publica el progrés d'un informe a la tasca de Celery (estat PROGRESS), que la cua
    d'informes llegeix per mostrar la barra. Només cada `every` elements i a l'últim,
    per no escriure a la bbdd de resultats a cada iteració. Sense tasca no fa res.
    """
    if not task or (current % every and current != total):
        return
    task.update_state(
        state='PROGRESS',
        meta={
            'current': current,
            'total': total,
            'percent': round((current / total) * 100, 2) if total else 0.0,
        },
    )
