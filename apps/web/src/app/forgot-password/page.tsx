import { Suspense } from "react";

import { AccountRecoveryCard } from "@/components/account-recovery-card";

export default function ForgotPasswordPage() {
  return (
    <Suspense>
      <AccountRecoveryCard mode="forgot" />
    </Suspense>
  );
}
