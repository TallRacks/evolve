import { ProductionDetail } from "@/components/production-pages";

export default async function Page({params}:{params:Promise<{id:string}>}){return <ProductionDetail id={(await params).id} platform/>}
