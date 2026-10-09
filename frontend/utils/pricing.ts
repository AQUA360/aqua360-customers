export const BillingPeriodDataTypeChoices = {
    'diaria': 'date.daily',
    'mensual': 'date.monthly',
    'quadrimestral': 'date.quadrimestral',
    'trimestral': 'date.trimestral',
    'bimestral': 'date.bimestral',
    'semestral': 'date.semestral',
    'anual': 'date.annual'
  };    
 

export const PriceDataTypeChoices = {
    'fixed': 'pricing_block.fixed',
    'prop': 'pricing_block.prop',
    'interval': 'pricing_block.interval',
    'variable': 'pricing_block.variable',
    'for': 'pricing_block.for',
  };

export const UnitsDataTypeChoices = {
  'm3': 'm3',
  'dm': 'service_block.diameter',
}

export const AdjustmentOperationDataTypeChoices = {
  'min': 'pricing_block.min',
  'max': 'pricing_block.max',
  'ptg': 'pricing_block.ptg',
  'ext': 'pricing_block.ext',
  'var': 'pricing_block.variable_contract',
  'set': 'common.assign',
}

export const VariableCalculationDataTypeChoices = {
  'consum': 'billing_block.consumption',
  'prev_consum': 'billing_block.previous_consumption',
  'dies_consum': 'billing_block.consumption_days',
  'diferencia_fuita': 'pricing_block.leak_diff',
  'diferencia_fuita_consum': 'pricing_block.leak_diff_consumption',
}

export const VariableCalculationConditionsDataTypeChoices = {
  'consum': 'billing_block.consumption',
  'dies_consum': 'billing_block.consumption_days',
  'diferencia_fuita': 'pricing_block.leak_diff',
  'diferencia_fuita_consum': 'pricing_block.leak_diff_consumption',
  'units': 'pricing_block.units',
  /* 'price': 'common.price', */
}

export const AdjustmentTypeChoices = {
  'DAYS': 'pricing_block.adj_days',
  /* 'MONTHS': 'Correcció per mesos', */
  'NOADJ': 'pricing_block.no_adj',
}