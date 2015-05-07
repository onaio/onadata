def parse_int(num):
    try:
        return num and int(num)
    except ValueError:
        pass
