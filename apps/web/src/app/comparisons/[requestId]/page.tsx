import { AppShell } from "@/components/app-shell";
import { ComparisonResult } from "@/components/comparison-workspace";

export default async function ComparisonPage({
  params,
}: {
  params: Promise<{ requestId: string }>;
}) {
  const { requestId } = await params;
  return (
    <AppShell>
      <ComparisonResult requestId={requestId} />
    </AppShell>
  );
}
