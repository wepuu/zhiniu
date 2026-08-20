import { AppShell } from "@/components/app-shell";
import { ResearchFeedDashboard } from "@/components/research-feed-dashboard";

export default function Home() {
  return (
    <AppShell>
      <ResearchFeedDashboard />
    </AppShell>
  );
}
