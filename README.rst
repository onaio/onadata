  Ona Platform
=================
Collect, Analyze and Share Data!

.. image:: https://magnum.travis-ci.com/onaio/core.svg?token=zuW2DmA3xKoPXEdebzpS&branch=master
  :target: https://magnum.travis-ci.com/repositories

About
-----

Ona is derived from the excellent `formhub <http://github.com/SEL-Columbia/formhub>`_ platform developed by the Sustainable Engineering Lab at Columbia University.

Installation
------------

See `install.md <install.md>`_.

Contributing
------------

If you would like to contribute code please read
`Contributing Code to Ona Data <https://github.com/onaio/onadata/wiki/Contributing-Code-to-OnaData>`_.

Edit top level requirements in the file `requirements/base.in <requirements/base.in>`_. Use
 `pip-compile <https://github.com/nvie/pip-tools>`_ to update `requirements/base.pip <requirements/base.pip>`_,

.. code-block:: sh

    $ pip-compile --output-file requirements/base.pip requirements/base.in

Code Structure
--------------

* **api** - This app provides the API functionality mostly made up of viewsets

* **logger** - This app serves XForms to and receives submissions from
  ODK Collect and Enketo.

* **viewer** - This app provides a csv and xls export of the data stored in
  logger. This app uses a data dictionary as produced by pyxform. It also
  provides a map and single survey view.

* **main** - This app is the glue that brings logger and viewer
  together.

Localization
------------

To generate a locale from scratch (ex. Spanish)

.. code-block:: sh

    $ django-admin.py makemessages -l es -e py,html,email,txt ;
    $ for app in {main,viewer} ; do cd onadata/apps/${app} && django-admin.py makemessages -d djangojs -l es && cd - ; done

To update PO files

.. code-block:: sh

    $ django-admin.py makemessages -a ;
    $ for app in {main,viewer} ; do cd onadata/apps/${app} && django-admin.py makemessages -d djangojs -a && cd - ; done

To compile MO files and update live translations

.. code-block:: sh

    $ django-admin.py compilemessages ;
    $ for app in {main,viewer} ; do cd onadata/apps/${app} && django-admin.py compilemessages && cd - ; done

Api Documentation
-----------------

.. code-block:: sh

    $ cd docs
    $ make html
    $ python manage.py collectstatic

Django Debug Toolbar
--------------------

* `$ pip install django-debug-toolbar`
* Use/see `onadata/settings/debug_toolbar_settings/py`
* Access api endpoint on the browser and use `.debug` as the format extension e.g `/api/v1/projects.debug`

Upgrading existing installation to django 1.9+
----------------------------------------------

**Requirements**
* Postgres 9.4 or higher
* xcode-select version 2343 or higher

**Upgrading from a pervious Ona setup**
Ensure you upgrade all your pip requirements using the following command:

.. code-block:: sh

    pip install -r requirements/base.pip

Fake initial migration of `guardian`, `django_digest`, `registration`. Migrate `contenttypes` app first.

.. code-block:: sh

    $ python manage.py migrate contenttypes
    $ python manage.py migrate --fake-initial django_digest
    $ python manage.py migrate --fake-initial guardian
    $ python manage.py migrate --fake-initial registration
    $ python manage.py migrate


**Major django changes affecting Ona**
* The DATABASES settings key depricates the use of the *autocommit* setting in the *OPTIONS* dictionary.
