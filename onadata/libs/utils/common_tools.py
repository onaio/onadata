import six
import uuid


def str_to_bool(s):
    """Return boolean True or False if string s represents a boolean value"""
    # no need to convert boolean values otherwise it will always be false
    if isinstance(s, bool):
        return s

    TRUE_VALUES = ['TRUE', 'T', '1', 1]
    s = s.upper() if isinstance(s, six.string_types) else s

    return s in TRUE_VALUES


def get_boolean_value(str_var, default=None):
    if isinstance(str_var, basestring) and \
            str_var.lower() in ['true', 'false']:
        return str_to_bool(str_var)

    return str_var if default else False


def getUUID():
    '''
    Return UUID
    '''
    return uuid.uuid4().hex
