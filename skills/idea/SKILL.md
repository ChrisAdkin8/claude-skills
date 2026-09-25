---
name: idea
description: Capture a new idea as a markdown note in ~/notes/ideas using the idea template. Use when the user runs /idea, or asks to capture, save, jot down or note an idea for later.
argument-hint: <short description of the idea>
allowed-tools: Read(~/notes/**), Edit(~/notes/**), Bash(git rev-parse *), Bash(git -C ~/notes add *), Bash(git -C ~/notes commit *)
---

# Capture an idea

The idea: $ARGUMENTS

Capture should be fast. File the note, don't interrogate the user or start developing the idea unless they ask.

1. **Get the idea.** If nothing was passed above, use the idea just discussed in the conversation. If there is none, ask for it in one line.
2. **Check for duplicates.** Search `~/notes/ideas/` for notes with similar titles or key terms. If there is a close match, ask whether to add to that note instead of creating a new one.
3. **Create the note** at `~/notes/ideas/YYYY-MM-DD-short-slug.md` (today's date, 3–6 word lowercase hyphenated slug), starting from `~/notes/templates/idea.md`.
4. **Fill it in:**
   - `title`, `created` (today), `status: seed`.
   - `tags` following the conventions in `~/notes/CLAUDE.md`.
   - `related`: if the current working directory is a repo under `~/code`, add its path (e.g. `~/code/github.com/org/repo`).
   - "The idea": the user's own words, tidied but not reinterpreted.
   - Other sections: fill only with what the user said or the conversation established. Leave the rest as the template's prompts. Never invent content.
5. **Commit** only that note: `git -C ~/notes add <path>`, then `git -C ~/notes commit` with the message `idea: <title>`, following this session's commit attribution rules. Don't push.
6. **Report** the file path in one line. Optionally add one sharp open question worth thinking about, and mention that `/research <path>` will dig into it.
