# Contributing to EduBot (A Guide for Developers)

## Installation

### 1. Cloning the Repository

To grab the latest version of `EduBot` run the following command:

``` cmd
git clone https://github.com/TUDelft-CNS-ATM/EduBot.git
```

### 2. Creating and Activating a Virtual Environment

To ensure that the installation does not affect other projects, it is wise to
create a new local virtual environment. For this we will use the `venv` module,
however you are free to use `conda` if you wish.

``` cmd
py -3 -m venv .env
```

Once this command executes, the new environment must be activated as follows:

#### Windows

``` cmd
".env/Scripts/activate"
```

*Note: the quotation marks are important!*

#### Linux

``` bash
source .env/bin/activate
```

### 3. Installing an Editable Version of EduBot

Next, since this project uses the `src/` layout an editable version of the code
needs to be installed. This is accomplished by running the following command:

``` cmd
pip install -e .[dev]
```

Note that the `[dev]` specifier here installs some additional requirements
necessary for proper development such as a syntax checker and a formatter.
This must also be installed on the CI/CD pipeline VM.

## Cross-Platform / Cross-IDE Development

To ensure that the code indentation, spacing, and line-endings are normalized
across all platforms and IDE's an `.editorconfig` file is used. Make sure that
your editor supports this configuration file by checking the [editorconfig]
website. Depending on your editor you may need to install a plug-in/extension
which is the case currently for [Visual Studio Code].

## Code Formatting

To preserve a uniform look across the entire project and make it easy to get
good looking code [flake8], [black], and [isort] are used. All of the required
packages for this and their respective extensions will be installed if the
`[dev]` specifier is added when installing `EduBot`. Configuration settings of
these tools are housed in the [setup.cfg] and [pyproject.toml] files.

## Future Improvements (Help Needed!)

Refer to the un-asigned open [Issues] tagged with `enhancement` for features
that need to be implemented in the current sprint.

<!-- Un-wrapped URL Links -->
[setup.cfg]: setup.cfg
[editorconfig]: https://editorconfig.org/
[Visual Studio Code]: https://code.visualstudio.com/
[flake8]: https://flake8.pycqa.org/en/latest/
[black]: https://black.readthedocs.io/en/stable/
[isort]: https://timothycrosley.github.io/isort/
[Issues]: https://github.com/TUDelft-CNS-ATM/EduBot/issues
[pyproject.toml]: pyproject.toml
