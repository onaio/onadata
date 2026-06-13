TEST_SETTINGS ?= onadata.settings.github_actions_test
TEST_LABELS ?=

blank:
	@echo "Downloading ona core dependencies and running migrations for you (hopefully into a virtualenv)... \n (This will take a while, go grab a coffee or something.)\n\n"
	python -m pip install -r requirements/base.pip
	python manage.py migrate
	@echo "Start the app with \`python manage.py runserver --nothreading\`"

test:
	python manage.py test $(TEST_LABELS) --settings=$(TEST_SETTINGS) --noinput

test-keepdb:
	python manage.py test $(TEST_LABELS) --settings=$(TEST_SETTINGS) --noinput --keepdb
