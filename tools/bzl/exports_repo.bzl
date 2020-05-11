# The file defines the exports_repo() bazel rule.


def _exports_repo_impl(ctx):
  # The script which will perform the export.
  deployment_script = ctx.actions.declare_file("{}.sh".format(ctx.attr.name))
  if not "workspace" in ctx.var:
    fail(
      "Running an exports_repo() rule requires defining the path of the "
      + "workspace. Use: --define=workspace=$(pwd)."
    )
  # Populate the export script.
  ctx.actions.write(
    output=deployment_script,
    is_executable=True,
    content="""\
set -e
# TODO(cec): I haven't figured out how to get the runfiles path of the 
# exports_repo dependency, so try and guess it. There is definitely a
# cleaner way of doing this, but this hack works for now (at least until
# someone tries changing the name of the workspace or bazel's runfiles
# layout changes).
if [[ -f "external/cec_exports_repo/exports_repo.par" ]]; then
  exports_repo="external/cec_exports_repo/exports_repo.par"
elif [[ -f "cec_exports_repo/exports_repo.par" ]]; then
  exports_repo="cec_exports_repo/exports_repo.par"
elif [[ -f "exports_repo.par" ]]; then
  exports_repo="exports_repo.par"
else
  echo "fatal: could not locate exports_repo.par in $(pwd)" >&2
  exit 1
fi

cat <<EOF | ./"$exports_repo"
{{
  "always_export_path": "{always_export_path}",
  "branch": "{branch}",
  "path_remove": [{path_remove}],
  "path_rename": {{{path_rename}}},
  "paths": [{paths}],
  "remote": "{remote}",
  "tag_rename": "{tag_rename}",
  "targets": [{targets}],
  "workspace": "{workspace}"
}}
EOF
""".format(
      always_export_path=ctx.attr.always_export_path,
      branch=ctx.attr.branch,
      path_remove=",".join(['"{}"'.format(t) for t in ctx.attr.path_remove]),
      path_rename=",".join(
        ['"{}": "{}"'.format(k, v) for k, v in ctx.attr.path_rename.items()]
      ),
      paths=",".join(['"{}"'.format(t) for t in ctx.attr.paths]),
      remote=ctx.attr.remote,
      tag_rename=ctx.attr.tag_rename,
      targets=",".join(['"{}"'.format(t) for t in ctx.attr.targets]),
      workspace=ctx.var["workspace"],
    ),
  )

  files = (
    [deployment_script]
    + ctx.files._exports_repo
    + ctx.attr._exports_repo.data_runfiles.files.to_list()
    + ctx.attr._exports_repo.default_runfiles.files.to_list()
  )

  runfiles = ctx.runfiles(files=files, collect_default=True, collect_data=True)

  return DefaultInfo(executable=deployment_script, runfiles=runfiles)


exports_repo = rule(
  attrs={
    "remote": attr.string(
      mandatory=True, doc="URL of the git repo to export to",
    ),
    "branch": attr.string(default="master", doc="The branch to push to",),
    "targets": attr.string_list(
      default=[], doc="bazel queries to be find targets to export",
    ),
    "paths": attr.string_list(default=[], doc="additional files to export",),
    "path_remove": attr.string_list(default=[], doc="files to remove",),
    "path_rename": attr.string_dict(default={}, doc="files to move on export",),
    "tag_rename": attr.string(default="", doc="a prefix for exported git tags"),
    "always_export_path": attr.string(
      default="tools/always_export.txt",
      doc="a file containing a list of paths to export",
    ),
    "_exports_repo": attr.label(
      executable=False,
      cfg="host",
      allow_files=True,
      default=Label("//:exports_repo.par"),
    ),
  },
  executable=True,
  implementation=_exports_repo_impl,
)
