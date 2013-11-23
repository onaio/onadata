OnaData
=======
Collect, Analyze and Share Data!

.. image:: https://secure.travis-ci.org/onaio/onadata.png?branch=master
  :target: http://travis-ci.org/onaio/onadata

About
-----

OnaData is derived from the excellent `formhub <http://github.com/SEL-Columbia/formhub>`_ platform developed by the Sustainable Engineering Lab at Columbia University.

Installation
------------
Please read the `Installation and Deployment Guide <https://github.com/modilabs/formhub/wiki/Installation-and-Deployment>`_.

Contributing
------------

If you would like to contribute code please read
`Contributing Code to Ona Data <https://github.com/onaio/onadata/wiki/Contributing-Code-to-OnaData>`_.

Code Structure
--------------

* odk_logger - This app serves XForms to ODK Collect and receives
  submissions from ODK Collect. This is a stand alone application.

* odk_viewer - This app provides a
  csv and xls export of the data stored in odk_logger. This app uses a
  data dictionary as produced by pyxform. It also provides a map and
  single survey view.

* main - This app is the glue that brings odk_logger and odk_viewer
  together.

Localization
------------

To generate a locale from scratch (ex. Spanish)

.. code-block:: sh

    $ django-admin.py makemessages -l es -e py,html,email,txt ;
    $ for app in {main,odk_viewer} ; do cd ${app} && django-admin.py makemessages -d djangojs -l es && cd - ; done

To update PO files

.. code-block:: sh

    $ django-admin.py makemessages -a ;
    $ for app in {main,odk_viewer} ; do cd ${app} && django-admin.py makemessages -d djangojs -a && cd - ; done

To compile MO files and update live translations

.. code-block:: sh

    $ django-admin.py compilemessages ;
    $ for app in {main,odk_viewer} ; do cd ${app} && django-admin.py compilemessages && cd - ; done
