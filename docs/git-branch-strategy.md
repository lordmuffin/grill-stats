# Git Branch Strategy

This document outlines the branch strategy for the Grill Stats project.

## Branch Types

### Main Branches

- **main**: The production-ready branch. All code in this branch should be stable and deployable.
- **develop**: The integration branch for features. This branch contains the latest delivered development changes.

### Supporting Branches

- **feature/***: Feature branches are used for developing new features. They branch off from `develop` and merge back into `develop` when the feature is complete.
- **bugfix/***: Bugfix branches are used to fix bugs. They branch off from `develop` and merge back into `develop` when the fix is complete.
- **hotfix/***: Hotfix branches are used to fix critical issues in production. They branch off from `main` and merge back into both `main` and `develop`.
- **release/***: Release branches are used to prepare for a production release. They branch off from `develop` and merge back into both `main` and `develop`.

## Workflow

1. **Feature Development**:
   - Create a new branch from `develop`: `git checkout -b feature/feature-name develop`
   - Make changes and commit: `git commit -m "Descriptive message"`
   - Push to remote: `git push -u origin feature/feature-name`
   - When complete, merge to develop: `git checkout develop && git merge --no-ff feature/feature-name`
   - Delete feature branch: `git branch -d feature/feature-name`

2. **Bug Fixes**:
   - Create a new branch from `develop`: `git checkout -b bugfix/bug-description develop`
   - Fix the bug and commit: `git commit -m "Fix: bug description"`
   - Push to remote: `git push -u origin bugfix/bug-description`
   - When complete, merge to develop: `git checkout develop && git merge --no-ff bugfix/bug-description`
   - Delete bugfix branch: `git branch -d bugfix/bug-description`

3. **Hotfixes**:
   - Create a new branch from `main`: `git checkout -b hotfix/issue-description main`
   - Fix the issue and commit: `git commit -m "Hotfix: issue description"`
   - Push to remote: `git push -u origin hotfix/issue-description`
   - When complete, merge to main: `git checkout main && git merge --no-ff hotfix/issue-description`
   - Also merge to develop: `git checkout develop && git merge --no-ff hotfix/issue-description`
   - Delete hotfix branch: `git branch -d hotfix/issue-description`

4. **Releases**:
   - Create a new branch from `develop`: `git checkout -b release/x.y.z develop`
   - Prepare for release (version bumps, etc.): `git commit -m "Prepare for release x.y.z"`
   - Push to remote: `git push -u origin release/x.y.z`
   - When complete, merge to main: `git checkout main && git merge --no-ff release/x.y.z`
   - Tag the release: `git tag -a vx.y.z -m "Release x.y.z"`
   - Also merge to develop: `git checkout develop && git merge --no-ff release/x.y.z`
   - Delete release branch: `git branch -d release/x.y.z`

## Best Practices

- Never commit directly to `main` or `develop` branches
- Use descriptive names for branches (e.g., `feature/add-temperature-alerts`)
- Keep branches short-lived and focused on a single task
- Regularly pull changes from `develop` into your feature branch to avoid merge conflicts
- Use meaningful commit messages following the conventional commits format
- Always delete branches after they have been merged

## Commit Message Format

Follow the conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- feat: A new feature
- fix: A bug fix
- docs: Documentation changes
- style: Code style changes (formatting, missing semi-colons, etc)
- refactor: Code changes that neither fix bugs nor add features
- perf: Performance improvements
- test: Adding or fixing tests
- chore: Changes to the build process or auxiliary tools

