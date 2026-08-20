import { AppShell } from "@/components/app-shell";
import { ResearchAlertSettings } from "@/components/research-alert-settings";
import { AdvancedAccessCard } from "@/components/advanced-access-card";

export default function SettingsPage() {
  return (
    <AppShell>
      <div className="mx-auto grid w-full max-w-5xl gap-6 py-8 lg:grid-cols-[1fr_1.15fr]">
        <AdvancedAccessCard />
        <ResearchAlertSettings />
      </div>
    </AppShell>
  );
}
