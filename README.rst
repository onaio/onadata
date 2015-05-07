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
Please read the `Installation and Deployment Guide <https://github.com/SEL-Columbia/formhub/wiki/Installation-and-Deployment>`_.

Contributing
------------

If you would like to contribute code please read
`Contributing Code to Ona Data <https://github.com/onaio/onadata/wiki/Contributing-Code-to-OnaData>`_.

Code Structure
--------------

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
