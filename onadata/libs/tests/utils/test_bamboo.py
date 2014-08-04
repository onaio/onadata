from mock import patch
from pybamboo.dataset import Dataset
from pybamboo.exceptions import ErrorParsingBambooData

from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.bamboo import get_new_bamboo_dataset


class TestBamboo(TestBase):
    @patch.object(Dataset, '__init__', side_effect=ErrorParsingBambooData())
    def test_get_new_bamboo_dataset_parse_error(self, mock):
        self._publish_transportation_form()
        self._make_submissions()

        ret = get_new_bamboo_dataset(self.xform)
        self.assertEqual(ret, u'')
