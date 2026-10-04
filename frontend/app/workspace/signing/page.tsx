import { SigningWorkspacePage } from "@/components/signing-pages";

export default async function Page({ searchParams }: { searchParams: Promise<{ document?: string; contract?: string }> }) {
  const params = await searchParams;
  return <SigningWorkspacePage initialDocument={params.document} initialContract={params.contract} />;
}
