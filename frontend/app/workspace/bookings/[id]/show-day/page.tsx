import { BookingShowDayPage } from "@/components/web-completion-pages";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  return <BookingShowDayPage id={(await params).id} />;
}
