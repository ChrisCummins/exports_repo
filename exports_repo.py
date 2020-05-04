"""Bazel subproject export.

This is a non-hemetic process which:

1. Identifies the subset of files that will be exported by evaluating the 
   source and build files of the listed `targets`.
2. Creates a temporary local clone of the current repository.
3. Re-writes the history of this clone to include only the subset of 
   required files.
4. Force-pushes the rewritten history to `remote/branch`.
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set

from cec_exports_repo_git_filter_repo import git_filter_repo


def GetAttributes() -> Dict[str, Any]:
  """Read the input attributes for this export."""
  return json.load(sys.stdin)


def PathFromLabel(label: str) -> Optional[str]:
  """Create a workspace relative path from a bazel label.

  Args:
  	A bazel label, e.g. "//foo:bar.cc".

  Returns:
  	A workspace-relative path, e.g. "foo/bar.cc". If the label does not resolve
  	to a path, returns None.
  """
  # First, filter only labels from within the current workspace.
  if not label.startswith("//"):
    return
  # Then, strip the leading '//' prefix.
  label = label[2:]
  # Strip the ':' prefix from top-level targets.
  if label.startswith(":"):
    return label[1:]
  # Finally, substitute the ':' target seperator with a '/' path separator.
  chars = list(label)
  chars[label.rfind(":")] = "/"
  return "".join(chars)


def BazelQuery(arg: str) -> List[str]:
  """Run bazel query and return a list of paths within this workspace.

  Args:
    arg: A query term.

  Returns:
    The list of paths returned by this query.
  """
  bazel_out = subprocess.check_output(
    ["bazel", "query", arg], stderr=subprocess.DEVNULL, universal_newlines=True
  )
  lines = [PathFromLabel(line) for line in bazel_out.rstrip().split("\n")]
  return [line for line in lines if line]


def FindDirAuxPaths(directory: str, visited: Set[str]) -> List[str]:
  """Find directory-level auxiliary files.

  Args:
	directory: A workspace-relative directory path.
	visited: A set of visited directories.

  Returns:
    A list of extra paths which should be exported.
  """
  aux = []

  while directory not in visited:
    visited.add(directory)
    find = (
      subprocess.check_output(
        [
          "find",
          directory,
          "-maxdepth",
          "1",
          "-iname",
          "LICENSE*",
          "-o",
          "-iname",
          "README*",
          "-o",
          "-iname",
          "CONTRIBUTING*",
          "-o",
          "-name",
          ".gitignore",
          "-o",
          "-name",
          "WORKSPACE",
          "-o",
          "-name",
          "DEPS.txt",
        ],
        stderr=subprocess.DEVNULL,
        universal_newlines=True,
      )
      .rstrip()
      .split("\n")
    )
    aux += [line[2:] if line.startswith("./") else line for line in find]
    directory = os.path.dirname(directory)
    # We have reached the parent of the workspace, stop.
    if not directory:
      break

  return [line for line in aux if line]


def ResolvePaths(
  paths: List[str],
  targets: List[str],
  path_remove: List[str],
  path_rename: Dict[str, str],
  always_export_path: str,
) -> List[str]:
  """Resolve a list of paths to export.

  Args:
    paths: A list of paths.
    targets: A list of bazel targets.
    path_remove: A list of paths to remove.
    path_rename: A map of path renames.
    always_export_path: The path of an always-export file. 

  Returns:
    A list of paths to export. Each path is known to exist.
  """
  paths = copy.copy(paths)

  # A list of files which should be exported if they are found. Basically these
  # are common bazel configuration files.
  paths += [
    ".bazelrc",
    ".bazelversion",
    "tools/bazel",
    "tools/bazel_env.sh",
  ]

  # Add the list of paths which are always exported.
  if os.path.isfile(always_export_path):
    with open(always_export_path) as f:
      paths += f.read().strip().split("\n")

  # Add the sources and build files for the additional targets.
  for target in targets:
    print(f"\r\033[KQuerying target {target} ... ", end="", file=sys.stderr)
    sys.stderr.flush()
    paths += BazelQuery(f'kind("source file", deps({target}))')
    paths += BazelQuery(f"buildfiles(deps({target}))")

  # Filter only those paths which exist.
  paths = list(set([path for path in paths if os.path.isfile(path)]))

  # Collect auxiliary files from directories.
  directories = set([os.path.dirname(path) or "." for path in paths])
  visited = set()
  for directory in directories:
    paths += FindDirAuxPaths(directory, visited)

  # Exclude paths that will later be overwritten by a path rename.
  paths = [path for path in paths if path not in path_rename.values()]

  # Add the sources for path renames.
  paths += list(path_rename.keys())

  # Filter paths to remove.
  paths = [path for path in paths if path not in path_remove]

  print("Enumerated paths to export:", len(paths), file=sys.stderr)
  return sorted(paths)


def FilterRepo(paths: List[str], tag_rename: str) -> None:
  """Rewrite repository history to include only specified files.

	Args:
		paths: The paths to preserve in history.
		tag_rename: A <new>:<old> rename pattern for tags.
	"""
  args = []
  for path in paths:
    args += ["--path", path]
  if tag_rename:
    args += ["--tag-rename", tag_rename]
  args.append("--force")
  args = git_filter_repo.FilteringOptions.parse_args(args)
  filter = git_filter_repo.RepoFilter(args)
  filter.run()


def RenamePaths(path_rename: Dict[str, str]) -> None:
  """Rename files by rewriting the git history.

	Args:
		path_rename: Files to rename. All paths are relative to repository 
			root.
	"""
  args = []
  for k, v in path_rename.items():
    args += ["--path-rename", f"{k}:{v}"]
  args.append("--force")
  args = git_filter_repo.FilteringOptions.parse_args(args)
  filter = git_filter_repo.RepoFilter(args)
  filter.run()


def Main(args):
  """Main entry point."""
  # Unpack input attributes.
  attr = GetAttributes()
  always_export_path = attr["always_export_path"]
  branch = attr["branch"]
  path_remove = attr["path_remove"]
  path_rename = attr["path_rename"]
  paths = attr["paths"]
  remote = attr["remote"]
  tag_rename = attr["tag_rename"]
  targets = attr["targets"]
  workspace = attr["workspace"]

  # Change to the workspace root to resolve paths.
  os.chdir(workspace)

  paths = ResolvePaths(
    paths, targets, path_remove, path_rename, always_export_path
  )
  print("   ", "\n    ".join(paths))

  with tempfile.TemporaryDirectory(prefix="cec_exports_repo_") as d:
    print("Creating a copy of this repository... ", end="", file=sys.stderr)
    sys.stderr.flush()
    subprocess.check_call(
      ["git", "clone", os.getcwd(), d], stderr=subprocess.DEVNULL
    )
    print("done", file=sys.stderr)

    # Change to the cloned repo before rewriting history.
    os.chdir(d)

    # Rewrite the repository history. Do this in two passes:
    #   The first strips unwanted files from the history.
    #   The second moves files around based on the path_rename arguments.
    #
    # The two passes is to prevent a conflict when rename a file where
    # both the source and destination exist, e.g. when renaming
    # foo/README to ./README, where both files exist in the history.
    print("Rewriting repo history...", file=sys.stderr)
    FilterRepo(paths, tag_rename)
    if path_rename:
      RenamePaths(path_rename)

    # Add a new remote to push the rewritten repo to.
    print("Pushing rewritten history to remote...", file=sys.stderr)
    subprocess.check_call(["git", "remote", "add", "push", remote])

    # Get the name of the current branch.
    current_branch = subprocess.check_output(
      ["git", "rev-parse", "--abbrev-ref", "HEAD"], universal_newlines=True
    ).rstrip()

    # Push the current branch to the remote repo.
    subprocess.check_call(
      ["git", "push", "--force", "push", f"{current_branch}:{branch}"]
    )


if __name__ == "__main__":
  Main(sys.argv[1:])
