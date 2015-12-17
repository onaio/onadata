from unittest import TestCase

from dict2xml import dict2xml
from onadata.libs.utils.dict_tools import csv_dict_to_nested_dict
from onadata.libs.utils.dict_tools import get_values_matching_key


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

    def test_lookup_path(self):
        doc = {
            u'fruits': u'carrot guava',
            u'end': u'2015-12-17T11:09:56.000+03:00',
            u'start': u'2015-12-17T11:08:41.000+03:00',
            u'points': [
                {
                    u'points/point': u'-13.859414 27.995911 0 0'
                },
                {
                    u'points/point': u'-12.897489 30.27832 0 0'
                }
            ],
            u'_xform_id_string': u'gps_in_repeats',
            u'meta/instanceID':
            u'uuid:340f7fe7-5d8e-451b-891f-09c8b3b44679'
        }
        fruits = list(get_values_matching_key(doc, 'fruits'))
        self.assertEqual(fruits, ['carrot guava'])
        points = list(get_values_matching_key(doc, 'points/point'))
        self.assertEqual(
            points,
            [
                u'-13.859414 27.995911 0 0',
                u'-12.897489 30.27832 0 0'
            ]
        )
