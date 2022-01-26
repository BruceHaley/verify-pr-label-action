#!/usr/bin/env python3

import os
import sys
import re
import distutils.util
from github import Github


def get_env_var(env_var_name, echo_value=False):
    """Try to get the value from a environmental variable.

    If the values is 'None', then a ValueError exception will
    be thrown.

    Args
    ----
    env_var_name : str
        The name of the environmental variable.
    echo_value : bool, optional, default False
        Print the resulting value.

    Returns
    -------
    value : str
        The value from the environmental variable.

    """
    value = os.environ.get(env_var_name)

    if value is None:
        print(f'ERROR: The environmental variable {env_var_name} is empty!',
              file=sys.stderr)
        sys.exit(1)

    if echo_value:
        print(f"{env_var_name} = {value}")

    return value


# Check if the number of input arguments is correct
if len(sys.argv) != 6:
    print('ERROR: Invalid number of arguments!', file=sys.stderr)
    sys.exit(1)

# Get the GitHub token
token = sys.argv[1]
if not token:
    print('ERROR: A token must be provided!', file=sys.stderr)
    sys.exit(1)

# Get the list of valid labels
valid_labels = [label.strip() for label in sys.argv[2].split(',')]
print(f'Valid labels are: {valid_labels}')

# Get the list of invalid labels
invalid_labels = [label.strip() for label in sys.argv[3].split(',')]
print(f'Invalid labels are: {invalid_labels}')

# Get the PR number
pr_number_str = sys.argv[4]

# Get needed values from the environmental variables
repo_name = get_env_var('GITHUB_REPOSITORY')
github_ref = get_env_var('GITHUB_REF')
github_event_name = get_env_var('GITHUB_EVENT_NAME')

# Create a repository object, using the GitHub token
repo = Github(token).get_repo(repo_name)

# When this actions runs on a "pull_reques_target" event, the pull request
# number is not available in the environmental variables; in that case it must
# be defined as an input value. Otherwise, we will extract it from the
# 'GITHUB_REF' variable.
if github_event_name == 'pull_request_target':
    # Verify the passed pull request number
    try:
        pr_number = int(pr_number_str)
    except ValueError:
        print('ERROR: A valid pull request number input must be defined when '
              'triggering on "pull_request_target". The pull request number '
              'passed was "{pr_number_str}".',
              file=sys.stderr)
        sys.exit(1)
else:
    # Try to extract the pull request number from the GitHub reference.
    try:
        pr_number = int(re.search('refs/pull/([0-9]+)/merge',
                        github_ref).group(1))
    except AttributeError:
        print('ERROR: The pull request number could not be extracted from '
              f'GITHUB_REF = "{github_ref}"', file=sys.stderr)
        sys.exit(1)

print(f'Pull request number: {pr_number}')

# Create a pull request object
pr = repo.get_pull(pr_number)

# Check if the PR comes from a fork. If so, the trigger must be
# 'pull_request_target'. Otherwise exit on error here.
if pr.head.repo.full_name != pr.base.repo.full_name:
    if github_event_name != 'pull_request_target':
        print('ERROR: PRs from forks are only supported when trigger on '
              '"pull_request_target"', file=sys.stderr)
        sys.exit(1)

# Get the pull request labels
pr_labels = pr.get_labels()

# This is a list of valid labels found in the pull request
pr_valid_labels = []

# This is a list of invalid labels found in the pull request
pr_invalid_labels = []

# Check which of the label in the pull request, are in the
# list of valid labels
for label in pr_labels:
    if label.name in valid_labels:
        pr_valid_labels.append(label.name)
    if label.name in invalid_labels:
        pr_invalid_labels.append(label.name)

# Check if there were not invalid labels and at least one valid label.
#
# Note: We do not generate reviews. Instead, we exit
# with an error code when no valid label or invalid labels are found, making
# the check fail. This will prevent merging the pull request. When a valid
# label and not invalid labels are found, we exit without an error code,
# making the check pass. This will allow merging the pull request.

# First, we check if there are invalid labels.
if pr_invalid_labels:
    print('Error! This pull request contains the following invalid labels: '
          f'{pr_invalid_labels}', file=sys.stderr)

    print('Exiting with an error code')
    sys.exit(1)
else:
    print('This pull request does not contain invalid labels')

# Then, we check it there are valid labels. This is done independently of the presence of
# invalid labels above.
if not pr_valid_labels:
    print('Error! This pull request must contain at least one of these labels: '
          f'{valid_labels}', file=sys.stderr)

    print('Exiting with an error code')
    sys.exit(1)
else:
    parity_label_conflict = False
    for label in pr_valid_labels:
        if "no parity" in label.name.lower():
            # A "no parity" label must not be accompanied by other parity labels.
            parity_label_conflict = len(pr_valid_labels) > 1

    if parity_label_conflict:
        print('Error! A "no parity" label cannot accompany other parity labels: '
            f'{pr_valid_labels}', file=sys.stderr)

        print('Exiting with an error code')
        sys.exit(1)
    else:
        forbidden_label = ""
        for label in pr_valid_labels:
            last_word = label.split()[-1]
            if last_word.lower() in repo_name.lower():
                forbidden_label = label

        if forbidden_label != "":
            print('Error! Label is not allowed to target this repo: '
                f'{forbidden_label}', file=sys.stderr)

            print('Exiting with an error code')
            sys.exit(1)
        else:
            print('This pull request contains the following valid labels: '
            f'{pr_valid_labels}')

    # Finally, we check if all labels are OK. This condition is complementary to the other
    # conditions above.
    if not pr_invalid_labels and pr_valid_labels:
        print('All labels are OK in this pull request')

        print('Exiting without an error code')
        sys.exit(0)
