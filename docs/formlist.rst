FormList endpoints
*************************

Implements OpenRosa API |FormListAPI|

.. |FormListAPI| raw:: html

    <a href="https://bitbucket.org/javarosa/javarosa/wiki/FormListAPI"
    target="_blank">here</a>

GET a list of forms
-------------------

These endpoints provide a discovery mechanism for returning the set of forms available for download.
The forms are filtered based upon the user's identity, where:

- ``form_pk`` - is the identifying number for a specific form
- ``user_name`` - username parameter allows filtering of forms to those owned by the user


.. raw:: html

    <pre class="prettyprint">
    <b>POST</b> /formList</pre>

Example
^^^^^^^
::

    curl -X GET https://api.ona.io/formList

Response:
::

<xforms>
<xform>
<formID>form_id</formID>
<name>name</name>
<version>202006121145</version>
<hash>md5:965fad0dbad4bb708d18abe77fcfe358</hash>
<descriptionText/>
<downloadUrl>https://api.ona.io/user_name/forms/form_pk/form.xml</downloadUrl>
</xform>
<xform>
<formID>testerform</formID>
<name>testerform</name>
<version>201904231241</version>
<hash>md5:a023b3535b7b593de1e9ad075e9e21e6</hash>
<descriptionText/>
<downloadUrl>https://api.ona.io/user_name/forms/form_pk/form.xml</downloadUrl>
<manifestUrl>https://api.ona.io/user_name/xformsManifest/1620</manifestUrl>
</xform>
</xforms>



Retreive a single form
----------------------

There a multiple endpoints that implement the ability to retrieve a Single XForm; The forms are divided by the filters they support:

GET /<username>/<form_pk>/formList

**Pass username and form pk**

Example
^^^^^^^
::

    curl -X GET https://api.ona.io/<user_name>/<form_pk>/formList

Filter formlist by ``user_name`` and ``form_pk``

Response:
::

<xforms>
<xform>
<formID>form_id</formID>
<name>name</name>
<version>202006121145</version>
<hash>md5:965fad0dbad4bb708d18abe77fcfe358</hash>
<descriptionText/>
<downloadUrl>https://api.ona.io/user_name/forms/form_pk/form.xml</downloadUrl>
</xform>
</xforms>



GET /enketo/<xform_pk>/formList


**Use enketo/<xform_pk> endpoint**

Example
^^^^^^^

::

    curl -X GET https://api.ona.io/enketo/<form_pk>/formList

Filter formlist by ``user_name`` and ``form_pk``, allowing for access to formlist by annonymous users


Response:
::

<xforms>
<xform>
<formID>form_id</formID>
<name>name</name>
<version>202006121145</version>
<hash>md5:965fad0dbad4bb708d18abe77fcfe358</hash>
<descriptionText/>
<downloadUrl>https://api.ona.io/user_name/forms/form_pk/form.xml</downloadUrl>
</xform>
</xforms>



GET /enketo-preview/<xform_pk>/formList

**Use enketo-preview/<xform_pk> endpoint**

Example
^^^^^^^

::

    curl -X GET https://api.ona.io/enketo-preview/<form_pk>/formList

Filter formlist by ``user_name`` and ``form_pk``, allowing for access to formlist by users without can-submit priviledges


Response:
::

<xforms>
<xform>
<formID>form_id</formID>
<name>name</name>
<version>202006121145</version>
<hash>md5:965fad0dbad4bb708d18abe77fcfe358</hash>
<descriptionText/>
<downloadUrl>https://api.ona.io/user_name/forms/form_pk/form.xml</downloadUrl>
</xform>
</xforms>
