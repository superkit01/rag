import { DocumentDetailPage } from "@/components/pages/document-detail-page";

export default async function Page({ params }: { params: Promise<{ documentId: string }> }) {
  const { documentId } = await params;
  return <DocumentDetailPage documentId={documentId} />;
}
