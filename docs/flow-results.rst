
Flow Results Packages (Experimental)
************************************

Overview
--------

The ``/api/v1/flow-results/packages`` implements the flow results API specifications. See the documentation at `FLOW Results Specification <https://github.com/FLOIP/flow-results/blob/api-spec/api-specification.md>`_. This is the only endpoint that also uses the `JSON API specification <http://jsonapi.org/format/>`_. The Flow Results Package is processed by the library `floip-py <https://github.com/onaio/floip-py>`_.

The Flow Results package is still in its early stages and this implementation is more of a proof of concept. Not all types are supported, some field types not yet supported may be ignored and hence not appear in the resulting Flow Results Package. The transformations also attempt to fit the data as the existing underlying structure of XForms and XForm submissions.

When pushing in a Flow Results Responses Package, the ``row_id``, ``question_id`` and the ``response_id`` columns are the main fields that data is extracted from the rest are ignored.

It is expected that the ``row_id`` should be the same for records that represent one submission or interaction throw a full Flow. For example where a Flow captures the name, age and place of birth of persions in attendance, the ``row_id`` of a single persion should be the same.

::

        ...
        # first submission
        ["2018-01-23T11:42:16", 110, "enumerator_x", "name", "Rudy Rue", {}],
        ["2018-01-23T11:42:16", 110, "enumerator_x", "age", 30, {}],
        ["2018-01-23T11:42:16", 110, "enumerator_x", "place_of_birth", "Elburgon", {}],
        # second submission
        ["2018-01-23T11:42:16", 111, "enumerator_x", "name", "Elma Louie", {}],
        ["2018-01-23T11:42:16", 111, "enumerator_x", "age", 23, {}],
        ["2018-01-23T11:42:16", 111, "enumerator_x", "place_of_birth", "Turbo", {}],
        ...

Numeric ``question_id`` fields will fail to publish because they do not form valid XML tags.

The Flow Results Package profile, ``flow-results-package``, is not yet supported by `Datapackage <https://frictionlessdata.io/schemas/registry.json>`_ as such you may have to replace the default profile with ``data-package`` to validate with `Data Package <https://github.com/frictionlessdata/datapackage-py>`_.


Authentication
--------------

Authentication methods supported is as documented `here <authenticationi.html>`_.

