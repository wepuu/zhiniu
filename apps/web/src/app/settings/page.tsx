import { AppShell } from "@/components/app-shell";
import { ResearchAlertSettings } from "@/components/research-alert-settings";
import { AdvancedAccessCard } from "@/components/advanced-access-card";
import { AccountSecurityCard } from "@/components/account-security-card";
import { BetaFeedbackCard } from "@/components/beta-feedback-card";
import { BetaOnboardingCard } from "@/components/beta-onboarding-card";

export default function SettingsPage() {
  return (
    <AppShell>
      <div className="mx-auto grid w-full min-w-0 max-w-5xl gap-6 py-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] [&>*]:min-w-0">
        <AccountSecurityCard />
        <AdvancedAccessCard />
        <ResearchAlertSettings />
        <BetaOnboardingCard />
        <BetaFeedbackCard />
      </div>
    </AppShell>
  );
}
