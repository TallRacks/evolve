import { InvitePage } from "@/components/management-pages";
export default async function Page({ params }: { params: Promise<{ token: string }> }) {
  return <InvitePage token={(await params).token} />;
}
