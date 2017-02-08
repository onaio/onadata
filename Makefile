blank:
	@echo "Downloading ona core dependencies and running migrations for you (hopefully into a virtualenv)... \n (This will take a while, go grab a coffee or something.)\n\n"
	python2 -m pip install -r requirements/base.pip
	python2 -m pip install -r requirements/dev.pip
	python2 manage.py migrate
	@echo "Start the app with \`python2 manage.py runserver --nothreading\`"
