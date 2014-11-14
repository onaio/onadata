from django.test import TransactionTestCase

from onadata.libs.serializers.attachment_serializer import get_path


class TestAttachmentSerializer(TransactionTestCase):

    def setUp(self):
        """
        self.data is a json represenatation of an xform
        """
        self.data = {
            "name": "photo_in_group",
            "title": "photo_in_group",
            "type": "survey",
            "default_language": "default",
            "id_string": "photo_in_group",
            "sms_keyword": "photo_in_group",
            "children": [
                {
                    "label": "Group #1",
                    "type": "group",
                    "children": [
                        {
                            "label": "Group #2",
                            "type": "group",
                            "children": [
                                {
                                    "type": "photo",
                                    "name": "photograph",
                                    "label": "Smile :)"
                                }
                            ],
                            "name": "group2"
                        }
                    ],
                    "name": "group1"
                },
                {
                    "control": {
                        "bodyless": True
                    },
                    "type": "group",
                    "children": [
                        {
                            "bind": {
                                "readonly": "true()",
                                "calculate": "concat('uuid:', uuid())"
                            },
                            "type": "calculate",
                            "name": "instanceID"
                        }
                    ],
                    "name": "meta"
                }
            ]
        }
        self.question = "photograph"

    def test_get_field_xpath_of_an_object(self):
        path = get_path(self.data, self.question)
        self.assertEquals(path, "group1/group2/photograph")
