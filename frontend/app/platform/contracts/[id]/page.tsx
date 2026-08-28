import { ContractDetailPage } from "@/components/contract-pages";

export default async function Page({params}:{params:Promise<{id:string}>}) { return <ContractDetailPage id={(await params).id} platform/>; }
