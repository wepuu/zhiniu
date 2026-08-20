import { Suspense } from "react";

import { AccountRecoveryCard } from "@/components/account-recovery-card";

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <AccountRecoveryCard mode="verify" />
    </Suspense>
  );
}
