# EDSL remote object commands

```bash
ep inspect survey.ep
ep push survey.ep --alias example-survey --description "Example survey" --visibility private
ep metadata survey.ep
ep update-metadata survey.ep --description "Updated description" --visibility unlisted
ep share survey.ep --user collaborator@example.com
ep shared survey.ep
ep unshare survey.ep --user collaborator@example.com
ep pull survey.ep
```

Use `ep <command> --help` for supported flags. The same operations are
available under `ep objects` where applicable. `ep push` and metadata updates
change remote state; command output reports the resulting object metadata.

For local persistence, use the object's `.git.save(...)` interface. Remote
package linkage is retained by `.ep` packages, allowing `ep pull` to update a
linked local package.
