# Initialize Parallel Worktrees

## Variables

FEATURE_NAME: $ARGUMENTS
NUMBER_OF_TREES: $ARGUMENTS

## Instructions

Create NUMBER_OF_TREES git worktrees for parallel development of FEATURE_NAME.

1. Create the trees directory if it doesn't exist
2. For each tree (1 to NUMBER_OF_TREES):
   - Create a new git worktree at `trees/FEATURE_NAME-{i}/`
   - Create a new branch named `FEATURE_NAME-{i}`
   - Copy environment files to each worktree
   - Set up development environment in each worktree

Each worktree will be an isolated copy of the codebase on its own branch, ready for independent development.

RUN `mkdir -p trees`

For each worktree:

```bash
git worktree add trees/FEATURE_NAME-1 -b FEATURE_NAME-1
git worktree add trees/FEATURE_NAME-2 -b FEATURE_NAME-2
git worktree add trees/FEATURE_NAME-3 -b FEATURE_NAME-3
```

Copy environment variables and setup each environment:

```bash
cp .env trees/FEATURE_NAME-1/.env 2>/dev/null || true
cp .env trees/FEATURE_NAME-2/.env 2>/dev/null || true
cp .env trees/FEATURE_NAME-3/.env 2>/dev/null || true
```

List the created worktrees:
RUN `git worktree list`
