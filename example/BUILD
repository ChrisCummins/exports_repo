load("@cec_exports_repo//tools/bzl:exports_repo.bzl", "exports_repo")

exports_repo(
    name = "export",
    path_remove = [
        "README.md",
    ],
    path_rename = {
        "example/README": "README",
    },
    remote = "git@github.com:ChrisCummins/exports_repo_example.git",
    targets = ["//example/..."],
)

cc_binary(
    name = "foo",
    srcs = ["foo.cc"],
)
