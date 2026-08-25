import { ProductionFormPage } from "@/components/production-pages";

export default async function Page({searchParams}:{searchParams:Promise<{booking?:string}>}){
  const {booking=""}=await searchParams;
  return <ProductionFormPage initialBooking={booking}/>;
}
