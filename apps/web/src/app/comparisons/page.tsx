import { AppShell } from "@/components/app-shell";
import { ComparisonLauncher } from "@/components/comparison-workspace";

export default async function ComparisonsPage({
  searchParams,
}: {
  searchParams: Promise<{ left?: string; right?: string }>;
}) {
  const { left = "", right = "" } = await searchParams;
  return (
    <AppShell>
      <ComparisonLauncher initialSymbol={left} initialRightSymbol={right} />
    </AppShell>
  );
}
