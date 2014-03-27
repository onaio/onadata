def str2bool(v):
    return v.lower() in (
        'yes', 'true', 't', '1') if isinstance(v, basestring) else v
