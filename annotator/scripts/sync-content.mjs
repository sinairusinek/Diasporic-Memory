// Copy data/annotator/ -> annotator/content/ before dev and build.
//
// The bundles are canonically produced into data/ (repo convention), but
// Vercel builds with Root Directory = annotator/, and files outside the root
// are not reliably available to the build or the serverless bundle. Copying is
// less clever than a symlink or a ../../ import and it is the thing that works
// identically on a laptop and on Vercel.
import { cp, mkdir, rm, stat } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, '../../data/annotator');
const dest = resolve(here, '../content');

try {
  await stat(src);
} catch {
  // A `vercel` deploy run from this directory uploads annotator/ only, so
  // data/ is absent on the build machine — but content/ came up with the
  // upload and is already correct. Nothing to copy; that is not an error.
  try {
    await stat(resolve(dest, 'index.json'));
    console.log('sync-content: no data/annotator/ here; using uploaded content/');
    process.exit(0);
  } catch {
    console.error(
      `sync-content: ${src} does not exist.\n` +
        `Run the build pipeline first:  python code/annotator/build_all.py`
    );
    process.exit(1);
  }
}

await rm(dest, { recursive: true, force: true });
await mkdir(dest, { recursive: true });
// Scans live in Vercel Blob, not here; annotations are exports, not inputs.
await cp(src, dest, {
  recursive: true,
  filter: (p) =>
    !p.includes('/.cache') && !p.includes('/scans') && !p.endsWith('.tsv'),
});
console.log(`sync-content: ${src} -> ${dest}`);
