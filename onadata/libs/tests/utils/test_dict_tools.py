from unittest import TestCase


def list_to_dict(items, value):
    key = items.pop()

    result = {}
    bracket_index = key.find('[')
    if bracket_index > 0:
        value = [value]
        key = key[:bracket_index]

    result[key] = value

    if len(items):
        result = list_to_dict(items, result)

    return result


def merge_list_of_dicts(list_of_dicts):
    result = {}

    for d in list_of_dicts:
        for k, v in d.items():
            if isinstance(v, list):
                if k in result:
                    result[k] = [merge_list_of_dicts(result[k] + v)]
                else:
                    result[k] = [merge_list_of_dicts(v)]
            else:
                if k in result:
                    result[k] = merge_list_of_dicts([result[k], v])
                else:
                    result[k] = v

    return result


def csv_dict_to_nested_dict(a):
    results = []

    for key in a.keys():
        result = {}
        value = a[key]
        split_keys = key.split('/')

        if len(split_keys) == 1:
            result[key] = value
        else:
            result = list_to_dict(split_keys, value)

        results.append(result)

    return merge_list_of_dicts(results)


class TestDictTools(TestCase):
    maxDiff = None

    def test_csv_repeat_field_to_dict(self):
        a = {'repeat[1]/gender': 'female'}
        b = {'repeat': [{'gender': 'female'}]}
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)

        a = {'group/repeat[1]/gender': 'female'}
        b = {'group': {'repeat': [{'gender': 'female'}]}}
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)

        a = {'group/repeat[1]/groupb/gender': 'female'}
        b = {'group': {'repeat': [{'groupb': {'gender': 'female'}}]}}
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)

        a = {'repeata[1]/repeatb[1]/gender': 'female'}
        b = {'repeata': [{'repeatb': [{'gender': 'female'}]}]}
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)

        a = {
            'repeat[1]/gender': 'female',
            'repeat[1]/age': 10
        }
        b = {
            'repeat': [{
                'gender': 'female',
                'age': 10
            }]
        }
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)

        a = {
            'group/repeat[1]/gender': 'female',
            'group/repeat[1]/age': 10
        }
        b = {
            'group': {
                'repeat': [{
                    'gender': 'female',
                    'age': 10
                }]
            }
        }
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)

        a = {
            'group/repeat[1]/groupb/gender': 'female',
            'group/repeat[1]/groupb/age': 10
        }
        b = {
            'group': {
                'repeat': [{
                    'groupb': {
                        'gender': 'female',
                        'age': 10
                    }
                }]
            }
        }
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)

        a = {
            'repeata[1]/repeatb[1]/gender': 'female',
            'repeata[1]/repeatb[1]/name': 'Swan',
            'repeata[1]/repeatb[1]/age': 10
        }
        b = {
            'repeata': [{
                'repeatb': [{
                    'gender': 'female',
                    'name': 'Swan',
                    'age': 10
                }]
            }]
        }
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)

        a = {
            'repeat[1]/gender': 'female',
            'repeat[2]/gender': 'male'
        }
        b = {
            'repeat': [{
                'gender': 'female',
            }, {
                'gender': 'female',
            }]
        }
        import ipdb
        ipdb.set_trace()
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)
