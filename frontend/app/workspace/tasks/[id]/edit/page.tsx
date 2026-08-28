import { TaskFormPage } from "@/components/workflow-pages";

export default async function Page({params}:{params:Promise<{id:string}>}){return <TaskFormPage id={(await params).id}/>}
