load("@subpar//:subpar.bzl", "par_binary")

par_binary(
    name = "exports_repo",
    srcs = ["exports_repo.py"],
    visibility = ["//visibility:public"],
    deps = [
        "@cec_exports_repo_git_filter_repo//:git_filter_repo",
    ],
)
