from unittest import TestCase

from dict2xml import dict2xml


def list_to_dict(items, value):
    key = items.pop()

    result = {}
    bracket_index = key.find('[')
    if bracket_index > 0:
        value = [value]

    result[key] = value

    if len(items):
        result = list_to_dict(items, result)

    return result


def merge_list_of_dicts(list_of_dicts):
    result = {}

    for d in list_of_dicts:
        for k, v in d.items():
            if isinstance(v, list):
                rs = merge_list_of_dicts(result[k] + v if k in result else v)
                result[k] = rs if isinstance(rs, list) else [rs]
            else:
                if k in result:
                    if isinstance(v, dict):
                        result[k] = merge_list_of_dicts([result[k], v])
                    else:
                        result = [result, d]
                else:
                    result[k] = v

    return result


def remove_indices_from_dict(obj):
    if not isinstance(obj, dict):
        raise ValueError(u"Expecting a dict, found: {}".format(type(obj)))

    result = {}
    for key, val in obj.items():
        bracket_index = key.find('[')
        key = key[:bracket_index] if bracket_index > -1 else key
        val = remove_indices_from_dict(val) if isinstance(val, dict) else val
        if isinstance(val, list):
            _val = []
            for row in val:
                if isinstance(row, dict):
                    row = remove_indices_from_dict(row)
                _val.append(row)
            val = _val
        if key in result:
            result[key].extend(val)
        else:
            result[key] = val

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

    merged_dict = merge_list_of_dicts(results)

    return remove_indices_from_dict(merged_dict)


class TestDictTools(TestCase):
    maxDiff = None

    def test_csv_repeat_field_to_dict(self):
        a = {'repeat[1]/gender': 'female'}
        b = {'repeat': [{'gender': 'female'}]}
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)
        self.assertEqual(
            dict2xml(c),
            """
<repeat>
  <gender>female</gender>
</repeat>
            """.strip()
        )

        a = {'group/repeat[1]/gender': 'female'}
        b = {'group': {'repeat': [{'gender': 'female'}]}}
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)
        self.assertEqual(
            dict2xml(c),
            """
<group>
  <repeat>
    <gender>female</gender>
  </repeat>
</group>
            """.strip()
        )

        a = {'group/repeat[1]/groupb/gender': 'female'}
        b = {'group': {'repeat': [{'groupb': {'gender': 'female'}}]}}
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)
        self.assertEqual(
            dict2xml(c),
            """
<group>
  <repeat>
    <groupb>
      <gender>female</gender>
    </groupb>
  </repeat>
</group>
            """.strip()
        )

        a = {'repeata[1]/repeatb[1]/gender': 'female'}
        b = {'repeata': [{'repeatb': [{'gender': 'female'}]}]}
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)
        self.assertEqual(
            dict2xml(c),
            """
<repeata>
  <repeatb>
    <gender>female</gender>
  </repeatb>
</repeata>
            """.strip()
        )

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
        self.assertEqual(
            dict2xml(c),
            """
<repeat>
  <age>10</age>
  <gender>female</gender>
</repeat>
            """.strip()
        )

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
        self.assertEqual(
            dict2xml(c),
            """
<group>
  <repeat>
    <age>10</age>
    <gender>female</gender>
  </repeat>
</group>
            """.strip()
        )

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
        self.assertEqual(
            dict2xml(c),
            """
<group>
  <repeat>
    <groupb>
      <age>10</age>
      <gender>female</gender>
    </groupb>
  </repeat>
</group>
            """.strip()
        )

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
        self.assertEqual(
            dict2xml(c),
            """
<repeata>
  <repeatb>
    <age>10</age>
    <gender>female</gender>
    <name>Swan</name>
  </repeatb>
</repeata>
            """.strip()
        )

        a = {
            'repeat[1]/gender': 'female',
            'repeat[2]/gender': 'male'
        }
        b = {
            'repeat': [{
                'gender': 'female',
            }, {
                'gender': 'male',
            }]
        }
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)
        self.assertEqual(
            dict2xml(c),
            """
<repeat>
  <gender>female</gender>
</repeat>
<repeat>
  <gender>male</gender>
</repeat>
            """.strip()
        )

        a = {
            'repeat[1]/gender': 'female',
            'repeat[1]/age': 10,
            'repeat[2]/gender': 'male'
        }
        b = {
            'repeat': [{
                'gender': 'female',
                'age': 10
            }, {
                'gender': 'male',
            }]
        }
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)
        self.assertEqual(
            dict2xml(c),
            """
<repeat>
  <age>10</age>
  <gender>female</gender>
</repeat>
<repeat>
  <gender>male</gender>
</repeat>
            """.strip()
        )

        a = {
            'group/repeat[1]/gender': 'female',
            'group/repeat[1]/age': 10,
            'repeat[1]/gender': 'male'
        }
        b = {
            'group': {
                'repeat': [{
                    'gender': 'female',
                    'age': 10
                }]
            },
            'repeat': [{
                'gender': 'male',
            }]
        }
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)
        self.assertEqual(
            dict2xml(c),
            """
<group>
  <repeat>
    <age>10</age>
    <gender>female</gender>
  </repeat>
</group>
<repeat>
  <gender>male</gender>
</repeat>
            """.strip()
        )

        a = {
            'group/repeat[1]/gender': 'female',
            'group/repeat[1]/age': 10,
            'group/repeat[2]/gender': 'male'
        }
        b = {
            'group': {
                'repeat': [{
                    'gender': 'female',
                    'age': 10
                }, {
                    'gender': 'male',
                }]
            }
        }
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)
        self.assertEqual(
            dict2xml(c),
            """
<group>
  <repeat>
    <age>10</age>
    <gender>female</gender>
  </repeat>
  <repeat>
    <gender>male</gender>
  </repeat>
</group>
            """.strip()
        )

        a = {
            'repeata[1]/repeat[1]/groupb/gender': 'female',
            'repeata[1]/repeat[1]/groupb/age': 10,
            'repeata[1]/repeat[2]/groupb/gender': 'male',
            'repeata[2]/repeat[1]/groupb/gender': 'male'
        }
        b = {
            'repeata': [{
                'repeat': [{
                    'groupb': {
                        'gender': 'female',
                        'age': 10
                    }
                }, {
                    'groupb': {
                        'gender': 'male',
                    }
                }]
            }, {
                'repeat': [{
                    'groupb': {
                        'gender': 'male',
                    }
                }]
            }]
        }
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)
        self.assertEqual(
            dict2xml(c),
            """
<repeata>
  <repeat>
    <groupb>
      <age>10</age>
      <gender>female</gender>
    </groupb>
  </repeat>
  <repeat>
    <groupb>
      <gender>male</gender>
    </groupb>
  </repeat>
</repeata>
<repeata>
  <repeat>
    <groupb>
      <gender>male</gender>
    </groupb>
  </repeat>
</repeata>
            """.strip()
        )

        a = {
            'group/repeat[1]/groupb/gender': 'female',
            'group/repeat[1]/groupb/age': 10,
            'group/repeat[2]/groupb/gender': 'male'
        }
        b = {
            'group': {
                'repeat': [{
                    'groupb': {
                        'gender': 'female',
                        'age': 10
                    }
                }, {
                    'groupb': {
                        'gender': 'male',
                    }
                }]
            }
        }
        c = csv_dict_to_nested_dict(a)

        self.assertDictEqual(c, b)
        self.assertEqual(
            dict2xml(c),
            """
<group>
  <repeat>
    <groupb>
      <age>10</age>
      <gender>female</gender>
    </groupb>
  </repeat>
  <repeat>
    <groupb>
      <gender>male</gender>
    </groupb>
  </repeat>
</group>
            """.strip()
        )
