load(
  "@bazel_tools//tools/build_defs/repo:git.bzl",
  "git_repository",
  "new_git_repository",
)


def cec_exports_repo_deps():
  """Pull in dependencies of exports_repo rule.

  This function should be loaded and run from your WORKSPACE file:

    load("@cec_exports_repo//tools/bzl:deps.bzl", "cec_exports_repo_deps")
    cec_exports_repo_deps()
  """
  git_repository(
    name="subpar",
    commit="35bb9f0092f71ea56b742a520602da9b3638a24f",
    remote="https://github.com/google/subpar",
    shallow_since="1557863961 -0400",
  )

  new_git_repository(
    name="cec_exports_repo_git_filter_repo",
    build_file_content="""
py_binary(
	name = "git_filter_repo",
	srcs = ["git_filter_repo.py"],
	visibility = ["//visibility:public"],
)
""",
    commit="c0c37a7656404dcefff55e55b8f7a9662f9d959d",
    remote="https://github.com/newren/git-filter-repo.git",
    shallow_since="1586066537 -0700",
  )
