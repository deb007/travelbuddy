import subprocess
import sys


def run_git_command(command_list):
    """Run a git command and return its output as text, raising with helpful error."""
    result = subprocess.run(command_list, capture_output=True, text=True)
    if result.returncode != 0:
        print(
            f"❌ Git command failed:\n  {' '.join(command_list)}\n  Error: {result.stderr.strip()}"
        )
        sys.exit(1)
    return result.stdout.strip()


def get_last_two_tags():
    """Fetch the last two tags sorted by commit date."""
    run_git_command(["git", "fetch", "--tags", "--quiet"])
    tags = run_git_command(["git", "tag", "--sort=-creatordate"]).splitlines()
    if len(tags) < 2:
        print("❌ Not enough tags found to generate changelog.")
        sys.exit(1)
    return tags[1], tags[0]  # (previous_tag, latest_tag)


def get_commits_between_tags(old_tag, new_tag):
    """Get commit messages between two tags."""
    print(f"🔍 Checking commits between {old_tag} → {new_tag}")
    commits_output = run_git_command(
        [
            "git",
            "log",
            f"{old_tag}..{new_tag}",
            "--oneline",
            "--pretty=format:%h %s (%an)",
        ]
    )
    commits = commits_output.splitlines()
    if not commits:
        print(f"⚠️ No commits found between {old_tag} and {new_tag}.")
    return commits


def generate_changelog_prompt(commits, old_tag, new_tag):
    """Prepare a structured prompt for changelog generation."""
    prompt = f"""
Generate a concise, developer-friendly changelog for version `{new_tag}` based on these commits since `{old_tag}`.

### Commits:
{chr(10).join(f"- {commit}" for commit in commits)}

### Guidelines:
- Group related changes (e.g., Fixes, Features, Improvements, Docs)
- Write clean, readable entries
- Omit trivial or merge commits
- Do not repeat PR numbers or hashes unnecessarily

Now, generate the final changelog text.
"""
    return prompt.strip()


def main():
    old_tag, new_tag = get_last_two_tags()
    commits = get_commits_between_tags(old_tag, new_tag)
    if not commits:
        print("No commits found. Exiting gracefully.")
        return

    prompt = generate_changelog_prompt(commits, old_tag, new_tag)
    print("\n✅ Generated prompt (to send to LLM):\n")
    print(prompt)


if __name__ == "__main__":
    main()
