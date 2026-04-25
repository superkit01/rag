import { TaskDetailPage } from "@/components/pages/task-detail-page";

export default async function Page({ params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = await params;
  return <TaskDetailPage kind="ingestion" taskId={taskId} />;
}
