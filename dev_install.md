# Ona Core install for development purposes.


### Postgresql
See the [install.md](https://github.com/onaio/core/blob/master/install.md#database-setup)


### Core
##### Set up and start your virtual environment or sandbox.
`$ virtualenv <.venv>`  
`$ source <.venv>/bin/activate`  


##### Run the makefile for development purposes
`$ make development`  
Create a `onadata/settings/local_settings.py` file.  
`$ python manage.py runserver --nothreading`  

