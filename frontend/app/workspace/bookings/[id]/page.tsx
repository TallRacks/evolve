import { BookingDetailPage } from "@/components/booking-pages";
export default async function Page({ params }: { params: Promise<{ id: string }> }) { return <BookingDetailPage id={(await params).id}/>; }
