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

### 3. Code contributions / Pull requests 💻

Pull requests are wholeheartedly welcome!❤️ If you are unsure about how to make your first pull request, here are some helpful resources:

- [Creating a pull request](https://help.github.com/en/github/collaborating-with-issues-and-pull-requests/creating-a-pull-request)
- [How to create effective pull requests](https://dev.to/mpermar/how-to-create-effective-pull-requests-2m8e)

In order to make it easier for us to facilitate the smooth merging of your pull request, please make sure the following standards are met within your pull request.

- Ensure your git commits are signed. _Read about signing commits [here](https://help.github.com/en/github/authenticating-to-github/signing-commits)_
- Code & commits follow our [styleguides](#Styleguides).
- Implement / Update tests that need to be updated and ensure that they pass. _Running all the tests within this project may be tough and time consuming. But not to worry! On submission of the pull request, [Travis CI](https://travis-ci.org/) will run all the tests across our modules_.

With the above points in mind feel free to comment on one of our [beginner-friendly issues](https://github.com/onaio/onadata/issues?q=is%3Aissue+is%3Aopen+label%3A%22Good+First+Issue%22) expressing your intent to work on it.

## Styleguides

### Git commit messages

Git commits help communicate what has changed within the project. Making it easier to track down changes or implementation within the codebase. Before contributing please read the following article by [Chris Beams](https://chris.beams.io) on [How to Write a Git Commit Message](https://chris.beams.io/posts/git-commit/).

### Python styleguide

All python code should follow the [PEP 8 Style guide](https://www.python.org/dev/peps/pep-0008/).

Our codebase utilizes [flake8](https://pypi.org/project/flake8/), run the following command to make sure your code fits our styling standards.

```shell
    flake8 onadata --exclude=migrations,src,db_migrations,local_settings.py
```
