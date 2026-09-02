import { cp } from "node:fs/promises";

// Next's standalone output intentionally excludes these directories. Scalingo
// runs the standalone server directly, so copy public assets into the runtime
// artifact after every production build.
await cp("public", ".next/standalone/public", { recursive: true, force: true });
await cp(".next/static", ".next/standalone/.next/static", {
  recursive: true,
  force: true,
});
