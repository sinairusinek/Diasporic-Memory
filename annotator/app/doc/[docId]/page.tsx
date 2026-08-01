import { notFound } from 'next/navigation';
import DocHeader from '@/components/DocHeader';
import Sidebar from '@/components/Sidebar';
import Workspace from '@/components/Workspace';
import { getDoc, getIndex, getNeighbours } from '@/lib/corpus';
import { countsByDoc } from '@/lib/store';

export const dynamic = 'force-dynamic';

export default async function DocPage({
  params,
}: {
  params: Promise<{ docId: string }>;
}) {
  const { docId } = await params;
  const [doc, index, nav] = await Promise.all([
    getDoc(docId),
    getIndex(),
    getNeighbours(docId),
  ]);
  if (!doc) notFound();

  // The sidebar's annotation counts are the only reason this page touches the
  // database; a missing DATABASE_URL should not stop the corpus being readable.
  let counts: Record<string, number> = {};
  try {
    counts = await countsByDoc();
  } catch {
    counts = {};
  }

  const caseEntry = index.cases.find((c) => c.case_id === doc.case_id);

  return (
    <div className="shell">
      <Sidebar index={index} activeDocId={docId} counts={counts} />
      <main className="main">
        <DocHeader
          doc={doc}
          caseEntry={caseEntry}
          position={nav.position}
          total={nav.total}
        />
        <Workspace
          doc={doc}
          vocab={index.tags}
          prevId={nav.prev}
          nextId={nav.next}
        />
      </main>
    </div>
  );
}
