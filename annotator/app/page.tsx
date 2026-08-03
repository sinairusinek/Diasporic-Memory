import Catalogue from '@/components/Catalogue';
import { getIndex } from '@/lib/corpus';
import { countsByDoc } from '@/lib/store';

export const dynamic = 'force-dynamic';

export default async function Home() {
  const index = await getIndex();
  if (!index.docs.length) {
    return (
      <main style={{ padding: 40 }}>
        <h1>No documents built</h1>
        <p>
          Run <code>python code/annotator/build_all.py</code>, then{' '}
          <code>npm run sync</code>.
        </p>
      </main>
    );
  }

  // Annotation counts are decoration on the catalogue; a missing DATABASE_URL
  // should not stop the corpus being browsable.
  let counts: Record<string, number> = {};
  try {
    counts = await countsByDoc();
  } catch {
    counts = {};
  }

  return <Catalogue index={index} counts={counts} />;
}
