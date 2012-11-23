
import requests
from django.utils import simplejson

from restservice.RestServiceInterface import RestServiceInterface
from utils.logger_tools import ensure_bamboo_datasets_exists


class ServiceDefinition(RestServiceInterface):
    id = u'joined_bamboo'
    verbose_name = u'Joined Bamboo POST'

    def send(self, url, parsed_instance):

        xform = parsed_instance.instance.xform

        # create/complete datasets for repeats/form
        ensure_bamboo_datasets_exists(xform)

        # data is unique to all datasets. Extra columns will be ignored
        # by bamboo.
        post_data = simplejson.dumps(parsed_instance.to_dict_for_mongo())

        def send_update_to_bamboo(dataset, url, data):
            # per-dataset URL
            rurl = ("%(url)sdatasets/%(set)s" % {'url': url, 'set': dataset})
            # make the request. Should we do anything on failure?
            requests.put(rurl,
                         data=data,
                         headers={"Content-Type": "application/json"})

        # flat list of all datasets to submit data to.
        # we don't inlcude joined_datasets as those gets updated atomaticaly.
        all_datasets = [xform.bamboo_datasets.get('bamboo_id')] + \
                       [rd.get('bamboo_id')
                        for rd
                        in xform.bamboo_datasets.get('repeats').values()]

        for dataset in all_datasets:
            send_update_to_bamboo(dataset, url, post_data)
