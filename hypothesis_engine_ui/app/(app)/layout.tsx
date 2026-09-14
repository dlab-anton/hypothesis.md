import { AuthGuard } from "@/components/auth-guard";

export default function AppLayout({
  children,
  modal,
}: {
  children: React.ReactNode;
  modal: React.ReactNode;
}) {
  return (
    <AuthGuard>
      {children}
      {modal}
    </AuthGuard>
  );
}
