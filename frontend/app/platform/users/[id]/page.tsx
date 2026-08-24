import { UserAdminDetailPage } from "@/components/platform-pages";
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  return <UserAdminDetailPage id={(await params).id} />;
}
