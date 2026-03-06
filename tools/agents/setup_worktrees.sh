#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   tools/agents/setup_worktrees.sh [target_dir]
# Example:
#   tools/agents/setup_worktrees.sh ../GetMoreDone-agents

TARGET_DIR="${1:-../GetMoreDone-agents}"
mkdir -p "$TARGET_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: run this script inside a git repository."
  exit 1
fi

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

create_branch_if_missing() {
  local branch="$1"
  if git show-ref --verify --quiet "refs/heads/$branch"; then
    return 0
  fi
  git branch "$branch"
}

add_worktree_if_missing() {
  local path="$1"
  local branch="$2"
  if [ -d "$path/.git" ] || [ -f "$path/.git" ]; then
    echo "Skipping existing worktree: $path"
    return 0
  fi
  git worktree add "$path" "$branch"
}

CODE_BRANCH="codex/agent-code"
DOCS_BRANCH="codex/agent-docs"
GH_BRANCH="codex/agent-github"

create_branch_if_missing "$CODE_BRANCH"
create_branch_if_missing "$DOCS_BRANCH"
create_branch_if_missing "$GH_BRANCH"

add_worktree_if_missing "$TARGET_DIR/code" "$CODE_BRANCH"
add_worktree_if_missing "$TARGET_DIR/docs" "$DOCS_BRANCH"
add_worktree_if_missing "$TARGET_DIR/github" "$GH_BRANCH"

cat <<MSG

Worktrees ready:
- $TARGET_DIR/code   -> $CODE_BRANCH
- $TARGET_DIR/docs   -> $DOCS_BRANCH
- $TARGET_DIR/github -> $GH_BRANCH

Next:
1) Open 3 agent sessions, one per worktree.
2) Use prompts in .agents/prompts/*.md.
3) Require handoff notes in docs/changes/ for every agent handoff.
MSG
