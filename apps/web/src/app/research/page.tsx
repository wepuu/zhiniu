import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/page-heading";
import { ResearchCard } from "@/components/research-card";
import { researchNotes } from "@/lib/mock-data";

export default function ResearchPage() {
  return (
    <AppShell>
      <PageHeading
        eyebrow="Research archive"
        title="研究档案"
        description="结构化保存变化、风险、事件与证据；基础股票研究快照由所有用户共享。"
      />
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {researchNotes.map((note) => (
          <ResearchCard key={note.symbol} note={note} />
        ))}
      </div>
    </AppShell>
  );
}
