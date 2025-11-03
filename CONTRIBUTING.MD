# Contribution Guidelines

First off, thank you for thinking of contributing to this project! 🥳

The following is a set of guidelines for contributing to Ona Data. Following these guidelines helps to communicate that you respect the time of the maintainers and your intent to help develop this project.

## How to contribute

### 1. Report a bug 🐛

In case you have encountered any issue within the project, please make sure:

- You are using the [latest release](http://github.com/onaio/onadata/releases).
- You have setup the project according to the [Installation Documentation](https://api.ona.io/static/docs/install.html).

After confirming the above, make sure the issue has not been reported on our [issues page](https://github.com/onaio/onadata/issues). If it hasn't been reported, [open a ticket](https://github.com/onaio/onadata/issues/new) containing:

- Information about your system environment (Operating System, local settings, etc.).
- What you expected to happen, and what actually happened.
- Out of place / weird logs and any other interesting information
- All steps to reproduce the issue.

### 2. Suggest Enhancements or New Features ⚡

Feature and enhancement requests are always welcome! We ask you ensure the following details are provided while [opening a ticket](https://github.com/onaio/onadata/issues/new), in order to start a constructive discussion:

- Describe the feature/enhancement in detail.
- Explain why the feature/enhancement is needed.
- Describe how the feature/enhancement should work
- List any advantages & disadvantages of implementing the feature/enhancement

### 3. Development

This section will help you set up the Ona Data project locally for development and testing.

#### 3.1 Setting up the development environment 🧩

Before you begin, make sure you have the following prerequisites installed:

- Python 3.10+
- An active python virtual environment. [Learn how to activate virtual environments using Pyenv](https://realpython.com/intro-to-pyenv/#virtual-environments-and-pyenv)
- [Docker](https://docs.docker.com/engine/install/) and [Docker Compose v2](https://docs.docker.com/compose/migrate/) installed.

If you're not familiar with using XLSForm, please review the reference at [XLSForm.org](https://xlsform.org/en/). Ona Data forms are authored using XLSForm syntax.

Then, clone the repository and navigate into the project directory:

```sh
git clone https://github.com/onaio/onadata.git
cd onadata
```

Install the development requirements in your local virtual environment by executing in the terminal

```sh
pip install -r requirements/dev.pip
```

Install the pre-commit hooks by running:

```sh
pre-commit install
```

Spin up the containers

```sh
docker compose up -d
```

Run the database migrations by running

```sh
docker compose exec api python manage.py migrate
```

You can now visit http://localhost:8000.

#### 3.2 Adding a new package

New packages are added via `pip-compile` provided by the [pip-tools](https://pypi.org/project/pip-tools/) package. Install this package in your environment.

To add a new package, update the corresponding `requirements/<environment>.in` depending on the package's purpose.

Available environments in `requirements/` include:

- `base`: Core runtime dependencies used by the application.
- `dev`: Tooling for local development and testing.
- `docs`: Dependencies for building project documentation.
- `s3`: Extras for the AWS S3 storage backend.
- `ses`: Extras for the AWS SES email backend.
- `azure`: Extras for Azure storage/email integrations.

Compile the corresponding `<environment>.pip` by running the command

```sh
pip-compile --output-file=requirements/<environment>.pip requirements/<environment>.in
```

e.g `pip-compile --output-file=requirements/base.pip requirements/base.in`

After making these changes, rebuild your Docker image:

```sh
docker compose down
docker compose build
docker compose up
```

To uninstall a package remove the package from the `.in` file and compile. Finally rebuild the image.

#### 3.3 Running tests

To run all tests

```sh
docker compose exec -e DB_HOST=database api python manage.py test --settings=onadata.settings.github_actions_test
```

To run tests on a specific module

```sh
docker compose exec -e DB_HOST=database api python manage.py test onadata.apps.api.tests.viewsets.test_entity_list_viewset --settings=onadata.settings.github_actions_test
```

### 4. Code contributions / Pull requests 💻

Pull requests are wholeheartedly welcome!❤️ If you are unsure about how to make your first pull request, here are some helpful resources:

- [Creating a pull request](https://help.github.com/en/github/collaborating-with-issues-and-pull-requests/creating-a-pull-request)
- [How to create effective pull requests](https://dev.to/mpermar/how-to-create-effective-pull-requests-2m8e)

In order to make it easier for us to facilitate the smooth merging of your pull request, please make sure the following standards are met within your pull request.

- Ensure your git commits are signed. _Read about signing commits [here](https://help.github.com/en/github/authenticating-to-github/signing-commits)_
- Code & commits follow our [styleguides](#Styleguides).
- Implement / Update tests that need to be updated and ensure that they pass. _Running all the tests within this project may be tough and time consuming. But not to worry! On submission of the pull request, [GitHub actions](https://github.com/features/actions) will run all the tests across our modules_.

With the above points in mind feel free to comment on one of our [beginner-friendly issues](https://github.com/onaio/onadata/issues?q=is%3Aissue+is%3Aopen+label%3A%22Good+First+Issue%22) expressing your intent to work on it.

## Styleguides

### Git commit messages

Git commits help communicate what has changed within the project. Making it easier to track down changes or implementation within the codebase. Before contributing please read the following article by [Chris Beams](https://chris.beams.io) on [How to Write a Git Commit Message](https://chris.beams.io/posts/git-commit/).

### Python styleguide

All python code should follow the [PEP 8 Style guide](https://www.python.org/dev/peps/pep-0008/).

All code is automatically formatted on commit using [pre-commit hooks](https://pre-commit.com/). This ensures consistent styling and formatting across all code contributions.
