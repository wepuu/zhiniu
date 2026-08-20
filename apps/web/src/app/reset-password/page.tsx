import { Suspense } from "react";

import { AccountRecoveryCard } from "@/components/account-recovery-card";

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <AccountRecoveryCard mode="reset" />
    </Suspense>
  );
}
