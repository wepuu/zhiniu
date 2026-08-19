import { AuthCard } from "@/components/auth-card";
import { Suspense } from "react";

export default function LoginPage() {
  return (
    <Suspense>
      <AuthCard mode="login" />
    </Suspense>
  );
}
