import { DocumentDetailPage } from "@/components/calendar-document-pages";
export default async function Page({params}:{params:Promise<{id:string}>}){return <DocumentDetailPage id={(await params).id}/>}
