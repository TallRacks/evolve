import { ProductionFormPage } from "@/components/production-pages";

export default async function Page({params}:{params:Promise<{id:string}>}){return <ProductionFormPage id={(await params).id}/>}
