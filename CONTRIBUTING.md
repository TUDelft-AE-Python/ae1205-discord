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

## Best-Practices

### Code Formatting

To preserve a uniform look across the entire project [flake8] along with the
[black] code formatter are used. This is especially important when working with
multiple developers as everyone usually has their own formatting tastes.
However, as with all joint endeavors the way forward is through compromise...or
in this case an auto-formatter with a heavy hand. All of the required packages
and their respect extensions will be automatically installed if the `[dev]`
specifier is added when installing `EduBot`.

### Git Commits

To have a rich history to the commits that are easily understood by all devs,
the following best-practices that are widely accepted/used in open-source
projects are adopted.

#### The seven rules of a great Git commit message

1. Separate subject from body with a blank line
2. Limit the subject line to 50 characters
3. Capitalize the subject line
4. Do not end the subject line with a period
5. Use the imperative mood in the subject line
6. Wrap the body at 72 characters
7. Use the body to explain what and why vs. how

The most important rule is to have a descriptive subject line that is written
in the imperative mood such that you can read the history as `This commit
will...{add subject line here}`. Therefore, past tense needs to be avoided and
subject lines starting with `Changed, Added, Modified` should be replaced with
`Change, Add, Modify`. Thus, an example commit would be as follows:

``` git
Add main.py to easily run the bot

This commit adds a main.py module that makes it a lot easier to initialize and
run the bot. Before, the bot would need to be imported from multiple files
which made it difficult for hosting the bot on the cloud.

Therefore, this module takes care of these imports and runs the bot using the
bot.run command.

Closes: #1
```

More information on these best-practices can be obtained from: [git-commits]

### Git Branches and Releases

At the moment two main branches exist in the GitHub repository: `master` and
`develop`. All development should take place on the `develop` branch where
stable changes are later merged with the `master` branch to form a new release.

The following steps should be followed during the creation of a new release.

1. Test the correct function of the bot by running the test-suite on the
   develop branch (To be developed later)
2. Update [CHANGELOG.md] with information pertaining to the new release
3. Create a commit titled `Update CHANGELOG for release X.Y.Z` and tag it with
   a new git tag labeled with `vX.Y.Z`. This is required for `setup.py` to pick
   up on the new release version when installing the bot.
4. Checkout the `master` branch and merge the `develop` branch into it
5. Form a GitHub release with the commit tag created in **Step 3** and copy
   the latest relevent changes from [CHANGELOG.md] into the release body.

*In the future, this process can be automated with CI/CD tools, but due to the
short time-frame of the initial release, automation will be dealt with later.*

## Future Improvements (Help Needed!)

Refer to the un-asigned open [Issues] tagged with `enhancement` for features
that need to be implemented in the current sprint.

<!-- Un-wrapped URL Links -->
[setup.cfg]: setup.cfg
[editorconfig]: https://editorconfig.org/
[Visual Studio Code]: https://code.visualstudio.com/
[git-commits]: https://chris.beams.io/posts/git-commit/
[flake8]: https://flake8.pycqa.org/en/latest/
[black]: https://black.readthedocs.io/en/stable/
[CHANGELOG.md]: CHANGELOG.md
[Issues]: https://github.com/TUDelft-CNS-ATM/EduBot/issues
