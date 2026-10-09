import os
from logger.models import LogContractChange
from ..models import Adjustment, AdjustmentIntervalStretch, AdjustmentCondition, BillingRange, LineItemType, PriceInterval, PriceIntervalStretch, PriceVariableInterval, PriceVariableIntervalStretch
from coredata.models import ConfigProject

#Duplicate line item types to new billing range
def billing_range_duplicate(user, prev_billing_range_id, new_billing_range_id):
    billing_range = BillingRange.objects.get(id=prev_billing_range_id)
    line_item_types = LineItemType.objects.filter(billing_range=billing_range)

    for line_item_type in line_item_types:
        adjustments = Adjustment.objects.filter(line_item_type=line_item_type)
        new_adjustments = []
        
        price_stretches = []
        variable_stretches = []
        new_price_interval = None
        new_price_variable_interval = None
        # Diccionaris per mapejar els stretches originals als nous
        price_stretch_mapping = {}
        variable_stretch_mapping = {}
        
        if line_item_type.price_interval:
            price_stretches = PriceIntervalStretch.objects.filter(price_interval=line_item_type.price_interval)
            new_price_interval = None
            new_price_interval = PriceInterval.objects.create(
                token=line_item_type.price_interval.token,
                units=line_item_type.price_interval.units,
                is_active=line_item_type.price_interval.is_active,
            )
        if line_item_type.price_variable:
            variable_stretches = PriceVariableIntervalStretch.objects.filter(price_variable_interval=line_item_type.price_variable)
            new_price_variable_interval = PriceVariableInterval.objects.create(
                token=line_item_type.price_variable.token,
                units=line_item_type.price_variable.units,
                is_active=line_item_type.price_variable.is_active,
            )
        
        for price_stretch in price_stretches:
            new_price_stretch = PriceIntervalStretch.objects.create(
                token=price_stretch.token + str(new_billing_range_id),
                name_stretch=price_stretch.name_stretch,
                price_interval=new_price_interval,
                price=price_stretch.price,
                proportional_price=price_stretch.proportional_price,
                stretch=price_stretch.stretch,
                end_stretch=price_stretch.end_stretch,
                article=price_stretch.article,
                code=price_stretch.code,
                is_active=price_stretch.is_active,
            )
            price_stretch_mapping[price_stretch] = new_price_stretch
        
        for variable_stretch in variable_stretches:
            new_variable_stretch = PriceVariableIntervalStretch.objects.create(
                token=variable_stretch.token + str(new_billing_range_id),
                name_stretch=variable_stretch.name_stretch,
                price_variable_interval=new_price_variable_interval,
                price=variable_stretch.price,
                proportional_price=variable_stretch.proportional_price,
                stretch=variable_stretch.stretch,
                end_stretch=variable_stretch.end_stretch,
                article=variable_stretch.article,
                code=variable_stretch.code,
                is_active=variable_stretch.is_active,
            )
            variable_stretch_mapping[variable_stretch] = new_variable_stretch
        
        new_line_item = LineItemType.objects.create(
            token=line_item_type.token + str(new_billing_range_id),
            name=line_item_type.name,
            price=line_item_type.price,
            proportional_price=line_item_type.proportional_price,
            price_interval=new_price_interval,
            price_variable=new_price_variable_interval,
            billing_range=BillingRange.objects.get(id=new_billing_range_id),
            billing_period=line_item_type.billing_period,
            quantity=line_item_type.quantity,
            tax=line_item_type.tax,
            is_active=line_item_type.is_active,
            article=line_item_type.article,
            code=line_item_type.code,
            formula=line_item_type.formula,
            operation=line_item_type.operation,
            active_choice=line_item_type.active_choice,
            inactive_choice=line_item_type.inactive_choice,
            is_positive=line_item_type.is_positive,
            is_prorated=line_item_type.is_prorated,
            always_show=line_item_type.always_show,
        )
        
        for adjustment in adjustments:
            new_adjustment = Adjustment.objects.create(
                token=adjustment.token + str(new_billing_range_id),
                name=adjustment.name,
                start_at=adjustment.start_at,
                end_at=adjustment.end_at,
                operation=adjustment.operation,
                variable_calculation=adjustment.variable_calculation,
                variable_type=adjustment.variable_type,
                quantity=adjustment.quantity,
                formula=adjustment.formula,
                position=adjustment.position,
                line_item_type=new_line_item,
                is_active=adjustment.is_active
            )
            new_adjustments.append(new_adjustment)
            
            # Duplicar AdjustmentIntervalStretch relacionats
            adjustment_interval_stretches = AdjustmentIntervalStretch.objects.filter(adjustment=adjustment)
            for adjustment_interval_stretch in adjustment_interval_stretches:
                # Trobar els nous stretches corresponents utilitzant el mapping
                new_price_interval_stretch = None
                new_price_variable_stretch = None
                
                if adjustment_interval_stretch.price_interval_stretch:
                    new_price_interval_stretch = price_stretch_mapping.get(adjustment_interval_stretch.price_interval_stretch)
                
                if adjustment_interval_stretch.price_variable_stretch:
                    new_price_variable_stretch = variable_stretch_mapping.get(adjustment_interval_stretch.price_variable_stretch)
                
                AdjustmentIntervalStretch.objects.create(
                    token=adjustment_interval_stretch.token + str(new_billing_range_id) if adjustment_interval_stretch.token else None,
                    adjustment=new_adjustment,
                    price_variable_stretch=new_price_variable_stretch,
                    price_interval_stretch=new_price_interval_stretch,
                    coefficient=adjustment_interval_stretch.coefficient,
                    formula=adjustment_interval_stretch.formula,
                )
            
            # Duplicar AdjustmentCondition relacionats
            adjustment_conditions = AdjustmentCondition.objects.filter(adjustment=adjustment)
            for adjustment_condition in adjustment_conditions:
                AdjustmentCondition.objects.create(
                    adjustment=new_adjustment,
                    name=adjustment_condition.name,
                    quantity=adjustment_condition.quantity,
                    operation=adjustment_condition.operation,
                    formula=adjustment_condition.formula,
                    position=adjustment_condition.position,
                )