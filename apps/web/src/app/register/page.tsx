import { AuthCard } from "@/components/auth-card";
import { Suspense } from "react";

export default function RegisterPage() {
  return (
    <Suspense>
      <AuthCard mode="register" />
    </Suspense>
  );
}
