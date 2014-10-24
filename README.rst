About
-----

kobocat is the data collection platform used in KoBoToolbox. It is based on the excellent `onadata <http://github.com/onaio/onadata>`_ platform developed by Ona LLC, which in itself is a redevelopment of the `formhub <http://github.com/SEL-Columbia/formhub>`_ platform developed by the Sustainable Engineering Lab at Columbia University.

Please refer to `dist-kobo-devel <https://github.com/kobotoolbox/dist-kobo-devel>`_ for  instructions on how to install KoBoToolbox.

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
    $ for app in {main,viewer} ; do cd kobocat/apps/${app} && django-admin.py makemessages -d djangojs -l es && cd - ; done

To update PO files

.. code-block:: sh

    $ django-admin.py makemessages -a ;
    $ for app in {main,viewer} ; do cd kobocat/apps/${app} && django-admin.py makemessages -d djangojs -a && cd - ; done

To compile MO files and update live translations

.. code-block:: sh

    $ django-admin.py compilemessages ;
    $ for app in {main,viewer} ; do cd kobocat/apps/${app} && django-admin.py compilemessages && cd - ; done
    
