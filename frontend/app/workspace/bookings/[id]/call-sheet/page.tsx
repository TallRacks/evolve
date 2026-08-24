import { BookingCallSheetPage } from "@/components/call-sheet-pages";
export default async function Page({params}:{params:Promise<{id:string}>}){return <BookingCallSheetPage bookingId={(await params).id}/>}
