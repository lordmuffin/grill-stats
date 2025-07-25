# Parallel Task Execution

## Variables
PLAN_TO_EXECUTE: $ARGUMENTS
NUMBER_OF_PARALLEL_WORKTREES: $ARGUMENTS

## Run these commands first
RUN `ls -la trees/`
RUN `git worktree list`
RUN `/mcp`
READ: PLAN_TO_EXECUTE

## MCPs
The agent's should utilize all available MCP's that are configured

## Instructions

We're going to create NUMBER_OF_PARALLEL_WORKTREES new subagents that use the Task tool to create N versions of the same feature in parallel.

This enables us to concurrently build the same feature in parallel so we can test and validate each subagent's changes in isolation then pick the best changes.

The first agent will run in trees/<feature_name>-1/
The second agent will run in trees/<feature_name>-2/
...
The last agent will run in trees/<feature_name>-<NUMBER_OF_PARALLEL_WORKTREES>/

The code in each worktree will be identical to the code in the current branch. It will be setup and ready for you to build the feature end to end.

Each agent will independently implement the engineering plan detailed in PLAN_TO_EXECUTE in their respective workspace.

When each subagent completes their work, have them report their final changes in a `RESULTS.md` file at the root of their respective workspace.

Make sure agents don't run start.sh or any other scripts that would start servers - focus on the code changes only.
