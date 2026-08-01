import { redirect } from 'next/navigation';
import { getIndex } from '@/lib/corpus';

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
  redirect(`/doc/${index.docs[0].doc_id}`);
}
