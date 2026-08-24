import { OrganizationAdminDetailPage } from "@/components/platform-pages";
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  return <OrganizationAdminDetailPage id={(await params).id} />;
}
