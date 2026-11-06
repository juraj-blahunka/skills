#!/bin/sh
# Install the skills in this repo into Claude Code.
#
# 1. Remove every symlink in the Claude skills directory that points into this repo,
#    including stale ones left behind by renamed or deleted skills.
# 2. Symlink every directory in this repo that contains a SKILL.md.
#
# Usage: ./install.sh
# Override the target with CLAUDE_SKILLS_DIR (default: ~/.claude/skills).

set -eu

repo=$(cd "$(dirname "$0")" && pwd -P)
target=${CLAUDE_SKILLS_DIR:-"$HOME/.claude/skills"}

mkdir -p "$target"

for link in "$target"/* "$target"/.[!.]*; do
	[ -L "$link" ] || continue
	dest=$(readlink "$link")
	case $dest in
		/*) ;;
		*) dest="$target/$dest" ;;
	esac
	case $dest in
		"$repo" | "$repo"/*)
			rm "$link"
			echo "unlinked $(basename "$link")"
			;;
	esac
done

for skill in "$repo"/*/SKILL.md; do
	[ -f "$skill" ] || continue
	dir=$(dirname "$skill")
	name=$(basename "$dir")
	if [ -e "$target/$name" ] || [ -L "$target/$name" ]; then
		echo "skipped $name: $target/$name already exists and is not from this repo" >&2
		continue
	fi
	ln -s "$dir" "$target/$name"
	echo "linked $name"
done
