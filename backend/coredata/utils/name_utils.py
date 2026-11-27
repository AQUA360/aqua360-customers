import datetime


def generate_token(model_class, field='-id', *args, offset=1, **kwargs):
    token = ''
    now = datetime.datetime.now()
    #token += now.strftime("%y%m%d%H%M%S")
    token += now.strftime("%y%m%d")
    
    token += ''.join(args)

    last_instance = model_class.objects.order_by(field).first()
    
    if 'token' in field:
        next_id = (int(last_instance.token) if last_instance else 0) + offset
        print(next_id)
    else:
        next_id = (last_instance.id if last_instance else 0) + offset

    token += f'{next_id:03d}'[-3:]
    return token


def check_token_exists(token, model, repeat=0):
    if model.objects.filter(token=token).exists():
        repeat += 1
        new_token = token + str(repeat) if repeat == 0 else token[:-1] + str(repeat)
        return check_token_exists(new_token, model, repeat)
    return token


# Opcional, només a name_utils_personalized: contract_request_token_matches(token, **kwargs)
# retorna True si el token actual d'una ContractRequest encara és coherent amb les dades
# que el determinen (rep els mateixos kwargs que generate_token). Si el mòdul personalitzat
# no la defineix, el token d'una sol·licitud no es regenera mai automàticament.
contract_request_token_matches = None

# Permet personalitzar les funcions per client: si existeix name_utils_personalized,
# s'usen les seves generate_token i/o check_token_exists en lloc de les d'aquest mòdul.
try:
    from coredata.utils import name_utils_personalized
    if hasattr(name_utils_personalized, 'generate_token'):
        generate_token = name_utils_personalized.generate_token
    if hasattr(name_utils_personalized, 'check_token_exists'):
        check_token_exists = name_utils_personalized.check_token_exists
    if hasattr(name_utils_personalized, 'contract_request_token_matches'):
        contract_request_token_matches = name_utils_personalized.contract_request_token_matches
except ImportError:
    pass