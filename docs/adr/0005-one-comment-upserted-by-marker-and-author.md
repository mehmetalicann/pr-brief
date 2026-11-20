# 5. One comment, found by marker and author

## Status
Accepted (2026-11-19)

## Context
A bot that posts on every push buries the conversation. A marker alone could be spoofed by anyone
who quotes it in a comment.

## Decision
The comment starts with a hidden marker (`<!-- pr-brief:v1 -->`). It is updated in place only if it
starts with the marker and was written by `github-actions[bot]`; otherwise a new comment is
created. The marker is neutralised in everything the model returns.

## Consequences
One comment per pull request, edited on every push; other users' comments are never touched. If a
workflow posts with another identity (a PAT or an App token), the comment is not recognised and a
new one is created each run. The README workflow adds a per-PR `concurrency` group so two runs
started seconds apart cannot both create one.
