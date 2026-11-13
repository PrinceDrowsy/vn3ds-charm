-- busted's own default `.moon` loader (busted/modules/files/moonscript.lua)
-- compiles each *spec* file correctly, but MoonScript's own `require`
-- hook (registered by `moonscript.insert_loader()`, used whenever a spec
-- file itself `require`s another .moon module -- e.g. `require "util"`)
-- snapshots `package.moonpath` from `package.path` at the moment
-- `require "moonscript"` first runs. Since `--lpath` is applied to
-- `package.path` *after* busted's own startup already required
-- moonscript once, that snapshot is stale -- it doesn't see this
-- project's `src/engine/` modules at all, and any spec that requires a
-- real project module fails with a confusing MoonScript syntax error
-- (`'=' expected near '*'`, pointing at that module's own `export
-- */local *` line) that has nothing to do with the real problem.
--
-- Fix: rebuild the loader (and its `package.moonpath` snapshot) here,
-- in a `--helper` script, which busted runs *after* `--lpath` has
-- already extended `package.path`.
local moonscript = require("moonscript")
moonscript.remove_loader()
package.moonpath = nil
moonscript.insert_loader()
