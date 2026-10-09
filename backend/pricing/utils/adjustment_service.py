from pricing.models import Adjustment

def updateAdjustmentPreferences(adjustment_id, current_preference):
    current_adjustment = Adjustment.objects.get(id=adjustment_id)
    
    adjustments = Adjustment.objects.filter(line_item_type=current_adjustment.line_item_type)
    sorted_adjustments = sorted(adjustments, key=lambda adj: (adj.position is None, adj.position))
    new_preferences = list(range(1, len(sorted_adjustments) + 1))

    for idx, adjustment in enumerate(sorted_adjustments):
        if adjustment == current_adjustment:
            adjustment.position = current_preference  
        else:
            adjustment.position = new_preferences[idx] if adjustment.position != current_preference else adjustment.position
        
        adjustment.save()

    return current_adjustment
