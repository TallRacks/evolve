import { ContractPrintPage } from "@/components/contract-pages";

export default async function Page({params}:{params:Promise<{id:string}>}) { return <ContractPrintPage id={(await params).id}/>; }
