
This phase will define a file that describes actions we want to run and how to interpret it.
We want to build code incrementally, working on well defined parts, adding tests for those, reviewing the change, then committing and then adding more.

The file is named TESTING

It applies to all files at it's level in the source tree or lower.
  - conversely, if we look at foo/bar/baz/ball/bat/foo.c we might have a TESTING at and of the 5 directories. All of them apply

We will need a method to get the set of files in a PR. 
  - one way to do that is with  `git diff --name-only <ref>`. 
  - some companies will have other revision control systems, where they can compute
    this set of files with an API call. so we need to write the code so that getting the changed files is an interface with one default implemetation. Users will relink the tool with other implementations.  In a few days, we'll write one specifically for datadog.

We'll need a method to find the set of TESTING files that apply to the set of files changed in a PR.  Make it parameterizable for a different file name. When we expand this set of tools it's not clear if we will have more files with names other than TESTING, or if we will call it METADATA and have multiple capabilities in it.

The content of TESTING is going to be read in as a protobuf. We will use textproto format. We'll define the protobuf messages in the rest of this file.

The entire proto message is Testing

## Testing
- include: string, repeated
  We need an "include" capability. This will take the path of a file relative to the root of the source tree.
- presubmit: Presubmit, repeated

## Presubmit message
- include_regex: string, repeated.  If specified, files matching the regex are applicable to this presubmit block
- exclude_regex: string, repeated.  If specified, files matching are excluded. Exclues applies after include processing.
- check_action: string, repeated.  Acton name
- check_tests: string, repeated:  TestSuite name.

## Action message
- name: string, mandatory. test suite name
- command: string, mandatory.
  a command to run.  The string may contain {FILES} which expands all the file names in the PR in that place, or {EACH_FILE} which runs the command once for each file.
- machine_type: string, repeated.  If provided run only on a machine of the that type. If machine_type is not specified, we will run on a set of default machine types.

## TestSuite message
This defines a set of bazel test targets
- name: string, mandatory. test suite name
- tests: string, repeated.  Bazel test patterns
- test_args: string list.
- platform: string, repeated. Bazel platforms to test on


# code considerations.

We obviously want to set up test cases where we can specify all the inputs
and look for expected outputs. Features should be tested this way before resorting to live integration tests.

- a mock source file tree. We want to just have a list of paths and some content. Strawman by example:
```
/src/main/foo.c
/src/main/lib/bar.c
/src/main/TESTING <<<CONTENT
text ...
CONTENT
/src/common/baz.c
```
This way we can have a single file defining an entire source file tree with intermixed TESTING files to process.

A typical test would specify the mock file tree, a list of files in the change,
and a list of expected action/test names that would be executed.


# How it all works

Very often, we will declare Actions and TestSuites in one TESTING file and include those in another. That allows us to reuse common action definitions in many parts of the file tree.

### overall flow
- enumerate the files in the PR
- reduce that to a set of directories
- walk the source tree up building a set of TESTING files to read
- read and parse those test files.
- handle includes
- walk over all the Presubmit messages
  - apply include/exclude regexs against the set of files in the PR
  - if there are no matches after the regex processing, skip this message
- For each collected Presubmit, build a set of actions and testsuites
- if the action has multiple machine types, we need to duplicate for each type
- if a testsuite has either test_args or or platforms then we have to group by those and repeat the suite for each of those groupings.
- The FILES for the Actions come from the list of files that make it through the regex on each presubmit.

Then we aggregate this collected set of actions and testsuites to a minimal set of gitlab jobs to create
- If the same action was for on the same machine type from several different Presubmit
messages, then union the set of files together
- For all the TestSuite, group by test_args and platforms, then union all the bazel test patterns
- In the future we well add a sanitizer/checker for test_args. That's a module that each company may want to design locally based on their test infrastructure resources.
