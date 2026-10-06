This repository contains a collection of tools to enhance the gitlab experience.

But actually, the goal is to work with other runners, like buildkit too.
we just use gitlab as our first interaction point

# main concepts

- get away from the strict concept of gitlab jobs.
- focus on individual actions
  - actions might run a shell script, or specify bazel tests. We may add other types of actions.
  - actions are declared in TESTING.pb files near the code (ignore .gitlab-ci.yml)
- the files modified in a PR determine the set of actions to run
- actions depend on capabilities of runners
  - this maps directly into the way we specify machine images in gitlab
    and require them from jobs.
- combine test acdtions into as few/many runners as you need
  - actions must be able to run in parallel, or declared as exclusive

