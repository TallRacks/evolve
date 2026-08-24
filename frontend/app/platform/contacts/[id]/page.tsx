import { ContactDetailPage } from "@/components/relationship-pages";
export default async function Page({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <ContactDetailPage id={id} platform/>; }
