# Campus API (`campus.api`)

The `/api/v1` service: assignments, circles, files, hosted apps,
submissions, and timetable. Address collections directly
(`campus.api.assignments.list()`), single items by id
(`campus.api.circles["circle_ab12cd34"].get()`), and drill into
sub-resources (`... submissions["sub_1"].feedback.add(...)`).

All methods raise the mapped
[`APIError`][campus_python.errors.APIError] subclass on non-2xx
responses. Records deserialize to `campus.model` classes, except
files, which are plain validated dicts.

Note: `campus.model.*` types are documented in the
[campus repo](https://github.com/nyjc-computing/campus); signatures
here reference them without cross-links.

## Assignments

::: campus_python.api.v1.assignments.Assignments

## Circles

::: campus_python.api.v1.circles.Circles

## Files

The by-slug consumer surface (list / meta / content / upsert /
delete). Files are binary blobs addressed by a stable slug
(e.g. `apps/quest-dom`); slugs ride as raw path tails. Methods are
inherited from the shared
[`BySlugCollection`][campus_python.api.v1.byslug.BySlugCollection]
(see [Extending the SDK](../extending.md#by-slug-surfaces)); records are
plain dicts, not `campus.model` classes.

::: campus_python.api.v1.files.Files
    options:
      inherited_members: true
      filters:
        - "!^(make_path|make_url|client)$"

## HostedApps

Single-file HTML apps published to Campus app hosting.
Content-addressed server-side: replacing content under a slug keeps
the slug's address while serving the new version. Methods are
inherited from
[`BySlugCollection`][campus_python.api.v1.byslug.BySlugCollection];
records deserialize to `campus.model.HostedApp`. Unlike files,
upstream defaults content to `text/html` when no content type is
given.

::: campus_python.api.v1.hostedapps.HostedApps
    options:
      inherited_members: true
      filters:
        - "!^(make_path|make_url|client)$"

## Submissions

::: campus_python.api.v1.submissions.Submissions

## Timetable

::: campus_python.api.v1.timetable.Timetables

## ApiRoot

::: campus_python.api.v1.ApiRoot
