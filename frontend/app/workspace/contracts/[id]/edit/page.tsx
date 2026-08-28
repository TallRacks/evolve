import { ContractFormPage } from "@/components/contract-pages";

export default async function Page({params}:{params:Promise<{id:string}>}) { return <ContractFormPage id={(await params).id}/>; }
