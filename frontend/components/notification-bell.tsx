"use client";
import Link from "next/link";
import {useEffect,useState} from "react";
import {Bell} from "lucide-react";
import {apiRequest} from "@/lib/api/client";
export function NotificationBell(){const[count,setCount]=useState(0);useEffect(()=>{const load=()=>void apiRequest<{count:number}>("/api/notifications/unread-count/").then(x=>setCount(x.count)).catch(()=>{});load();window.addEventListener("focus",load);return()=>window.removeEventListener("focus",load)},[]);return <Link className="relative grid size-10 place-items-center rounded-md border border-neutral-800" href="/notifications" aria-label={`${count} unread notifications`}><Bell size={18}/>{count>0&&<span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-red-500 px-1 text-center text-xs text-white">{count>99?"99+":count}</span>}</Link>}
