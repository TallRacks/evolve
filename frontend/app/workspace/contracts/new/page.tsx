import { ContractFormPage } from "@/components/contract-pages";

export default async function Page({searchParams}:{searchParams:Promise<{booking?:string}>}) { return <ContractFormPage initialBooking={(await searchParams).booking}/>; }
