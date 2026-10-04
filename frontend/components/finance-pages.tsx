"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth/auth-provider";
import { hasOrganizationPermission } from "@/lib/auth/access";
import { RouteGuard } from "@/components/auth/route-guard";
import {
  buttonClass,
  EmptyState,
  fieldClass,
  PageHeader,
  secondaryButtonClass,
  StatCard,
  StatusBadge,
} from "@/components/ui/page";
import { apiRequest } from "@/lib/api/client";
import { promptAction } from "@/components/ui/action-dialog";

type Invoice = {
  id: string; organization: string; booking: string | null; booking_reference: string | null;
  invoice_number: string; status: string; financial_state: string;
  artist_name_snapshot: string; billed_to_name: string; billed_to_email: string;
  billed_to_address: string; issue_date: string | null; due_date: string | null;
  currency: string; subtotal: string; tax_amount: string; total_amount: string;
  amount_paid: string; balance_due: string; internal_notes: string;
  customer_notes: string; line_items: LineItem[]; allocations: Allocation[];
};
type LineItem = { id: string; description: string; quantity: string; unit_amount: string; line_total: string; sequence: number; category: string };
type Allocation = { id: string; payment: string; payment_reference: string; invoice: string; invoice_number: string; amount: string; created_at: string };
type Payment = { id: string; payment_reference: string; status: string; currency: string; amount: string; allocated_amount: string; remaining_amount: string; payment_date: string; method: string; external_reference: string; payer_name: string; notes: string; proof_document_id?: string | null; proof_document_name?: string | null; allocations: Allocation[] };
type Booking = { id: string; reference: string; title: string; artist: { stage_name: string }; currency?: string; performance_fee?: string | null };
type Summary = Record<string, { outstanding: string; paid: string; outstanding_count: number; overdue_count: number; paid_count: number }>;

function Workspace({ children }: { children: React.ReactNode }) {
  return <RouteGuard portal="workspace"><AppShell organizationScoped>{children}</AppShell></RouteGuard>;
}
function Platform({ children }: { children: React.ReactNode }) {
  return <RouteGuard portal="platform"><AppShell>{children}</AppShell></RouteGuard>;
}
function money(value: string, currency: string) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(Number(value));
}
function useOrganization() {
  return useAuth().activeOrganizationId;
}
function useFinanceManage() {
  const { session, activeOrganizationId } = useAuth();
  return hasOrganizationPermission(session, activeOrganizationId, "finance.manage");
}

export function FinanceOverviewPage() {
  const organizationId = useOrganization();
  const canManage = useFinanceManage();
  const [summary, setSummary] = useState<Summary>({});
  useEffect(() => { if (organizationId) void apiRequest<Summary>(`/api/finance/overview/?organization_id=${organizationId}`).then(setSummary); }, [organizationId]);
  return <Workspace><PageHeader eyebrow="Finance" title="Financial overview" actions={canManage?<div className="flex gap-2"><Link className={secondaryButtonClass} href="/workspace/finance/payments/new">Record payment</Link><Link className={buttonClass} href="/workspace/finance/invoices/new">New invoice</Link></div>:undefined}/><div className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{Object.entries(summary).map(([currency, values]) => <div className="contents" key={currency}><StatCard label={`${currency} outstanding`} value={money(values.outstanding, currency)}/><StatCard label={`${currency} overdue`} value={values.overdue_count}/><StatCard label={`${currency} paid invoices`} value={values.paid_count}/></div>)}</div>{!Object.keys(summary).length&&<div className="mt-7"><EmptyState title="No finance activity" detail="Create an invoice from a Booking to begin."/></div>}</Workspace>;
}

export function BookingFinanceSection({ bookingId }: { bookingId: string }) {
  const [items, setItems] = useState<Invoice[]>([]);
  useEffect(() => {
    void apiRequest<Invoice[]>(`/api/finance/invoices/?booking=${bookingId}`).then(setItems);
  }, [bookingId]);
  return <section className="evolve-panel p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold">Finance</h2><p className="mt-1 text-sm text-neutral-500">Invoices and payment status derived from Finance records.</p></div><Link className={buttonClass} href="/workspace/finance/invoices/new">Create invoice</Link></div><div className="mt-4 grid gap-3">{items.map(item=><Link className="flex flex-wrap justify-between gap-3 border-t border-neutral-800 pt-3 text-sm" href={`/workspace/finance/invoices/${item.id}`} key={item.id}><span>{item.invoice_number}</span><span>{item.financial_state}</span><span>{money(item.balance_due,item.currency)} outstanding</span></Link>)}{!items.length&&<p className="text-sm text-neutral-500">No invoices for this Booking.</p>}</div></section>;
}

export function InvoiceListPage({ platform = false }: { platform?: boolean }) {
  const organizationId = useOrganization(); const canManage = useFinanceManage(); const [items, setItems] = useState<Invoice[]>([]); const [search, setSearch] = useState(""); const [status, setStatus] = useState(""); const [promoter, setPromoter] = useState(""); const [event, setEvent] = useState("");
  useEffect(() => { const params = new URLSearchParams(); if (!platform && organizationId) params.set("organization_id", organizationId); if (search) params.set("search", search); if (status) params.set("status", status); if (promoter) params.set("promoter_name", promoter); if (event) params.set("event", event); void apiRequest<Invoice[]>(`/api/finance/invoices/?${params}`).then(setItems); }, [organizationId, platform, search, status, promoter, event]);
  const body = <><PageHeader eyebrow={platform?"Platform finance":"Finance"} title="Invoices" actions={!platform&&canManage?<Link className={buttonClass} href="/workspace/finance/invoices/new">New invoice</Link>:undefined}/><div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><input className={fieldClass} placeholder="Search invoice, Booking, Artist or billed party" value={search} onChange={(event)=>setSearch(event.target.value)}/><input className={fieldClass} placeholder="Filter promoter" value={promoter} onChange={(event)=>setPromoter(event.target.value)}/><input className={fieldClass} placeholder="Filter event" value={event} onChange={(event)=>setEvent(event.target.value)}/><select className={fieldClass} value={status} onChange={(event)=>setStatus(event.target.value)}><option value="">All workflow states</option>{["draft","issued","void","cancelled"].map(value=><option key={value}>{value}</option>)}</select></div><div className="mt-7 grid gap-3">{items.map(item=><Link className="grid gap-3 evolve-panel p-5 sm:grid-cols-[1fr_auto_auto_auto]" href={`${platform?"/platform":"/workspace"}/finance/invoices/${item.id}`} key={item.id}><div><p className="font-semibold">{item.invoice_number}</p><p className="text-sm text-neutral-500">{item.booking_reference??"Standalone"} / {item.billed_to_name}</p></div><StatusBadge positive={item.financial_state==="paid"}>{item.financial_state}</StatusBadge><span>{money(item.total_amount,item.currency)}</span><span>{money(item.balance_due,item.currency)} due</span></Link>)}{!items.length&&<EmptyState title="No invoices" detail="No invoices match the current filters."/>}</div></>;
  return platform?<Platform>{body}</Platform>:<Workspace>{body}</Workspace>;
}

export function NewInvoicePage() {
  const organizationId=useOrganization(); const router=useRouter(); const[bookings,setBookings]=useState<Booking[]>([]); const[message,setMessage]=useState("");
  useEffect(()=>{if(organizationId)void apiRequest<Booking[]>(`/api/bookings/?organization_id=${organizationId}`).then(setBookings)},[organizationId]);
  async function submit(event:FormEvent<HTMLFormElement>){event.preventDefault();const element=event.currentTarget;const form=new FormData(element);try{const invoice=await apiRequest<Invoice>(`/api/bookings/${form.get("booking_id")}/create-invoice/`,{method:"POST"});router.push(`/workspace/finance/invoices/${invoice.id}`)}catch(error){setMessage(error instanceof Error?error.message:"Unable to create invoice.")}}
  return <Workspace><PageHeader eyebrow="Finance" title="Create invoice from Booking" description="Commercial terms are copied once into a draft financial record. Later Booking changes do not rewrite the invoice."/><form className="mt-7 max-w-2xl space-y-5" onSubmit={submit}>{message&&<p className="text-sm text-red-300">{message}</p>}<label className="block text-sm text-neutral-400">Booking<select className={`mt-2 ${fieldClass}`} name="booking_id" required><option value="">Select Booking</option>{bookings.map(item=><option key={item.id} value={item.id}>{item.reference} / {item.artist.stage_name} / {item.title}</option>)}</select></label><button className={buttonClass}>Create draft invoice</button></form></Workspace>;
}

export function InvoiceDetailPage({ platform=false, print=false }:{platform?:boolean;print?:boolean}) {
  const{id}=useParams<{id:string}>(); const[data,setData]=useState<Invoice|null>(null); const[message,setMessage]=useState(""); const load=useCallback(()=>apiRequest<Invoice>(`/api/finance/invoices/${id}/`).then(setData),[id]); useEffect(()=>{void load()},[load]);
  async function addLine(event:FormEvent<HTMLFormElement>){event.preventDefault();const element=event.currentTarget;const form=new FormData(element);await apiRequest(`/api/finance/invoices/${id}/line-items/`,{method:"POST",body:JSON.stringify({description:form.get("description"),quantity:form.get("quantity"),unit_amount:form.get("unit_amount"),sequence:(data?.line_items.length??0)+1})});element.reset();await load()}
  async function saveDraft(event:FormEvent<HTMLFormElement>){event.preventDefault();const element=event.currentTarget;const form=new FormData(element);await apiRequest(`/api/finance/invoices/${id}/`,{method:"PATCH",body:JSON.stringify({billed_to_name:form.get("billed_to_name"),billed_to_email:form.get("billed_to_email"),billed_to_address:form.get("billed_to_address"),due_date:form.get("due_date")||null,tax_amount:form.get("tax_amount"),customer_notes:form.get("customer_notes"),internal_notes:form.get("internal_notes")})});setMessage("Draft invoice updated.");await load()}
  async function action(name:"issue"|"void"){const reason=name==="void"?await promptAction("Reason for voiding this invoice") : null;if(name==="void"&&!reason)return;try{await apiRequest(`/api/finance/invoices/${id}/${name}/`,{method:"POST",body:JSON.stringify(reason?{reason}:{})});await load()}catch(error){setMessage(error instanceof Error?error.message:"Unable to update invoice.")}}
  if(print)return <RouteGuard portal="workspace"><InvoicePrint invoice={data}/></RouteGuard>;
  const body=<>{data&&<PageHeader eyebrow={platform?"Platform finance":"Invoice"} title={data.invoice_number} description={`${data.billed_to_name} / ${data.booking_reference??"Standalone invoice"}`} actions={<div className="flex gap-2">{!platform&&<Link className={secondaryButtonClass} href={`/workspace/finance/invoices/${id}/print`}>Print</Link>}{data.status==="draft"&&<button className={buttonClass} onClick={()=>void action("issue")}>Issue</button>}{data.status==="issued"&&<button className={secondaryButtonClass} onClick={()=>void action("void")}>Void</button>}</div>}/>} {message&&<p className="mt-4 text-red-300">{message}</p>}{data&&<><div className="mt-7 grid gap-4 sm:grid-cols-4"><StatCard label="Workflow" value={data.status}/><StatCard label="Payment" value={data.financial_state}/><StatCard label="Total" value={money(data.total_amount,data.currency)}/><StatCard label="Balance" value={money(data.balance_due,data.currency)}/></div>{data.status==="draft"&&<form className="mt-8 grid gap-3 rounded-md border border-neutral-800 p-5 sm:grid-cols-2" onSubmit={saveDraft}><input className={fieldClass} name="billed_to_name" defaultValue={data.billed_to_name} placeholder="Billed party" required/><input className={fieldClass} name="billed_to_email" defaultValue={data.billed_to_email} placeholder="Billing email" type="email"/><textarea className="min-h-24 rounded-md border border-neutral-700 bg-neutral-950 p-3 sm:col-span-2" name="billed_to_address" defaultValue={data.billed_to_address} placeholder="Billing address"/><input className={fieldClass} name="due_date" defaultValue={data.due_date??""} type="date"/><input className={fieldClass} name="tax_amount" defaultValue={data.tax_amount} min="0" step="0.01" type="number"/><textarea className="min-h-24 rounded-md border border-neutral-700 bg-neutral-950 p-3" name="customer_notes" defaultValue={data.customer_notes} placeholder="Customer notes"/><textarea className="min-h-24 rounded-md border border-neutral-700 bg-neutral-950 p-3" name="internal_notes" defaultValue={data.internal_notes} placeholder="Internal notes"/><button className={buttonClass}>Save draft</button></form>}<section className="mt-8"><h2 className="font-semibold">Line items</h2><div className="mt-3 divide-y divide-neutral-800 rounded-md border border-neutral-800">{data.line_items.map(item=><div className="grid grid-cols-[1fr_auto_auto] gap-4 p-4" key={item.id}><span>{item.description}</span><span>{item.quantity} x {money(item.unit_amount,data.currency)}</span><strong>{money(item.line_total,data.currency)}</strong></div>)}</div>{data.status==="draft"&&<form className="mt-4 grid gap-3 sm:grid-cols-[1fr_8rem_10rem_auto]" onSubmit={addLine}><input className={fieldClass} name="description" placeholder="Description" required/><input className={fieldClass} name="quantity" type="number" min="0.001" step="0.001" defaultValue="1" required/><input className={fieldClass} name="unit_amount" type="number" min="0" step="0.01" required/><button className={buttonClass}>Add</button></form>}</section><section className="mt-8 grid gap-4 sm:grid-cols-2"><div><h2 className="font-semibold">Bill to</h2><p className="mt-3 text-neutral-300">{data.billed_to_name}</p><p className="whitespace-pre-line text-sm text-neutral-500">{data.billed_to_address}</p></div><div><h2 className="font-semibold">Dates</h2><p className="mt-3 text-sm">Issued: {data.issue_date??"Not issued"}</p><p className="text-sm">Due: {data.due_date??"Not set"}</p></div></section></>}</>;
  return platform?<Platform>{body}</Platform>:<Workspace>{body}</Workspace>;
}

function InvoicePrint({invoice}:{invoice:Invoice|null}){const[brand,setBrand]=useState("Evolve");useEffect(()=>{if(invoice){void apiRequest<{brand_name:string}>("/api/branding/current/?organization_id="+invoice.organization).then(value=>setBrand(value.brand_name));setTimeout(()=>window.print(),100)}},[invoice]);if(!invoice)return <p>Loading invoice...</p>;return <main className="mx-auto max-w-4xl bg-white p-10 text-black print:p-0"><header className="flex justify-between border-b border-black pb-6"><div><p className="font-semibold">{brand}</p><p className="mt-2 text-sm uppercase">Invoice</p><h1 className="text-3xl font-semibold">{invoice.invoice_number}</h1></div><div className="text-right"><p>{invoice.artist_name_snapshot}</p><p>{invoice.issue_date}</p></div></header><section className="mt-8"><h2 className="font-semibold">Bill to</h2><p>{invoice.billed_to_name}</p><p className="whitespace-pre-line">{invoice.billed_to_address}</p></section><table className="mt-8 w-full"><thead><tr className="border-b border-black text-left"><th>Description</th><th>Quantity</th><th>Unit</th><th className="text-right">Total</th></tr></thead><tbody>{invoice.line_items.map(item=><tr className="border-b border-neutral-300" key={item.id}><td className="py-3">{item.description}</td><td>{item.quantity}</td><td>{money(item.unit_amount,invoice.currency)}</td><td className="text-right">{money(item.line_total,invoice.currency)}</td></tr>)}</tbody></table><div className="ml-auto mt-6 w-72 space-y-2"><p className="flex justify-between"><span>Subtotal</span><strong>{money(invoice.subtotal,invoice.currency)}</strong></p><p className="flex justify-between"><span>Tax</span><strong>{money(invoice.tax_amount,invoice.currency)}</strong></p><p className="flex justify-between border-t border-black pt-2 text-lg"><span>Total</span><strong>{money(invoice.total_amount,invoice.currency)}</strong></p><p className="flex justify-between"><span>Balance due</span><strong>{money(invoice.balance_due,invoice.currency)}</strong></p></div><footer className="mt-12 border-t border-neutral-400 pt-4 text-sm"><p>Due: {invoice.due_date??"Not specified"}</p><p>{invoice.customer_notes}</p></footer></main>}

export function PaymentListPage({platform=false}:{platform?:boolean}){const organizationId=useOrganization();const canManage=useFinanceManage();const[items,setItems]=useState<Payment[]>([]);useEffect(()=>{const query=!platform&&organizationId?`?organization_id=${organizationId}`:"";void apiRequest<Payment[]>(`/api/finance/payments/${query}`).then(setItems)},[organizationId,platform]);const body=<><PageHeader eyebrow={platform?"Platform finance":"Finance"} title="Payments" actions={!platform&&canManage?<Link className={buttonClass} href="/workspace/finance/payments/new">Record payment</Link>:undefined}/><div className="mt-7 grid gap-3">{items.map(item=><Link className="grid gap-3 evolve-panel p-5 sm:grid-cols-[1fr_auto_auto_auto]" href={`${platform?"/platform":"/workspace"}/finance/payments/${item.id}`} key={item.id}><div><p className="font-semibold">{item.payment_reference}</p><p className="text-sm text-neutral-500">{item.payment_date} / {item.method.replaceAll("_"," ")}</p></div><StatusBadge positive={item.status==="recorded"}>{item.status}</StatusBadge><span>{money(item.amount,item.currency)}</span><span>{money(item.remaining_amount,item.currency)} remaining</span></Link>)}</div></>;return platform?<Platform>{body}</Platform>:<Workspace>{body}</Workspace>}

export function NewPaymentPage(){const organizationId=useOrganization();const router=useRouter();const[message,setMessage]=useState("");async function submit(event:FormEvent<HTMLFormElement>){event.preventDefault();const element=event.currentTarget;const form=new FormData(element);try{const payment=await apiRequest<Payment>("/api/finance/payments/",{method:"POST",body:JSON.stringify({organization_id:organizationId,currency:form.get("currency"),amount:form.get("amount"),payment_date:form.get("payment_date"),method:form.get("method"),external_reference:form.get("external_reference"),payer_name:form.get("payer_name"),notes:form.get("notes")})});router.push(`/workspace/finance/payments/${payment.id}`)}catch(error){setMessage(error instanceof Error?error.message:"Unable to record payment.")}}return <Workspace><PageHeader eyebrow="Finance" title="Record payment" description="Record external payment facts only. Never enter card or bank credentials."/><form className="mt-7 grid max-w-2xl gap-5 sm:grid-cols-2" onSubmit={submit}>{message&&<p className="sm:col-span-2 text-red-300">{message}</p>}<input className={fieldClass} name="amount" type="number" min="0.01" step="0.01" placeholder="Amount" required/><input className={fieldClass} name="currency" defaultValue="ZAR" maxLength={3} required/><input className={fieldClass} name="payment_date" type="date" required/><select className={fieldClass} name="method">{["bank_transfer","card_external","cash","mobile_money","cheque","other"].map(value=><option key={value}>{value}</option>)}</select><input className={fieldClass} name="external_reference" placeholder="External reference"/><input className={fieldClass} name="payer_name" placeholder="Payer name"/><textarea className="min-h-24 rounded-md border border-neutral-700 bg-neutral-950 p-3 sm:col-span-2" name="notes" placeholder="Notes"/><button className={buttonClass}>Record payment</button></form></Workspace>}

export function PaymentDetailPage({platform=false}:{platform?:boolean}){const{id}=useParams<{id:string}>();const[data,setData]=useState<Payment|null>(null);const[invoices,setInvoices]=useState<Invoice[]>([]);const load=useCallback(()=>apiRequest<Payment>(`/api/finance/payments/${id}/`).then(setData),[id]);useEffect(()=>{void load();void apiRequest<Invoice[]>("/api/finance/invoices/?status=issued").then(setInvoices)},[load]);async function allocate(event:FormEvent<HTMLFormElement>){event.preventDefault();const element=event.currentTarget;const form=new FormData(element);await apiRequest(`/api/finance/payments/${id}/allocations/`,{method:"POST",body:JSON.stringify({invoice_id:form.get("invoice_id"),amount:form.get("amount")})});await load()}async function uploadProof(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=new FormData(event.currentTarget);await apiRequest(`/api/finance/payments/${id}/proof/`,{method:"POST",body:form});await load()}const body=<>{data&&<PageHeader eyebrow={platform?"Platform finance":"Payment"} title={data.payment_reference} description={`${data.payment_date} / ${data.method.replaceAll("_"," ")}`}/>} {data&&<><div className="mt-7 grid gap-4 sm:grid-cols-3"><StatCard label="Amount" value={money(data.amount,data.currency)}/><StatCard label="Allocated" value={money(data.allocated_amount,data.currency)}/><StatCard label="Remaining" value={money(data.remaining_amount,data.currency)}/></div><section className="mt-8"><h2 className="font-semibold">Proof of payment</h2><p className="mt-2 text-sm text-neutral-500">Private receipt or POP stored in restricted document storage.</p>{data.proof_document_name&&<p className="mt-3 text-sm text-emerald-300">Attached: {data.proof_document_name}</p>}{!platform&&<form className="mt-4 flex flex-wrap gap-3" encType="multipart/form-data" onSubmit={uploadProof}><input className={fieldClass} name="file" type="file" accept="application/pdf,image/*" required/><button className={secondaryButtonClass}>Upload POP</button></form>}</section><section className="mt-8"><h2 className="font-semibold">Allocations</h2>{data.allocations.map(item=><div className="mt-3 flex justify-between border-b border-neutral-800 pb-3" key={item.id}><span>{item.invoice_number}</span><span>{money(item.amount,data.currency)}</span></div>)}{!platform&&Number(data.remaining_amount)>0&&<form className="mt-5 grid gap-3 sm:grid-cols-[1fr_10rem_auto]" onSubmit={allocate}><select className={fieldClass} name="invoice_id" required><option value="">Issued invoice</option>{invoices.filter(item=>item.currency===data.currency&&Number(item.balance_due)>0).map(item=><option key={item.id} value={item.id}>{item.invoice_number} / {money(item.balance_due,item.currency)} due</option>)}</select><input className={fieldClass} name="amount" type="number" min="0.01" step="0.01" max={data.remaining_amount} required/><button className={buttonClass}>Allocate</button></form>}</section></>}</>;return platform?<Platform>{body}</Platform>:<Workspace>{body}</Workspace>}


export function FinanceSettingsPage() {
  const organizationId = useOrganization();
  const canManage = useFinanceManage();
  const [message, setMessage] = useState('');
  const [data, setData] = useState<Record<string, string | number> | null>(null);
  useEffect(() => { if (organizationId) void apiRequest<Record<string, string | number>>(`/api/finance/profile/?organization_id=${organizationId}`).then(setData).catch((error) => setMessage(error instanceof Error ? error.message : 'Unable to load finance settings.')); }, [organizationId]);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organizationId || !canManage) return;
    const form = new FormData(event.currentTarget);
    try {
      const result = await apiRequest<Record<string, string | number>>('/api/finance/profile/', { method: 'PATCH', body: JSON.stringify({ organization_id: organizationId, legal_name: form.get('legal_name'), registration_number: form.get('registration_number'), tax_number: form.get('tax_number'), billing_email: form.get('billing_email'), billing_address: form.get('billing_address'), payment_terms: form.get('payment_terms'), invoice_prefix: form.get('invoice_prefix'), quote_prefix: form.get('quote_prefix'), next_invoice_number: Number(form.get('next_invoice_number')), next_quote_number: Number(form.get('next_quote_number')), default_currency: form.get('default_currency') }) });
      setData(result); setMessage('Finance profile saved. New invoices and quotes will use these details.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Unable to save finance settings.'); }
  }
  return <Workspace><PageHeader eyebrow="Finance / Configuration" title="Company billing details" description="Configure the legal, billing, numbering, and payment-term details used by invoices, quotes, and generated documents."/><form key={data ? JSON.stringify(data) : "empty"} className="mt-7 grid max-w-4xl gap-4 sm:grid-cols-2" onSubmit={save}>{message && <p className="sm:col-span-2 text-sm text-[var(--accent-strong)]">{message}</p>}<input className={fieldClass} name="legal_name" defaultValue={String(data?.legal_name ?? '')} placeholder="Legal company name" required/><input className={fieldClass} name="registration_number" defaultValue={String(data?.registration_number ?? '')} placeholder="Registration number"/><input className={fieldClass} name="tax_number" defaultValue={String(data?.tax_number ?? '')} placeholder="Tax / VAT number"/><input className={fieldClass} name="billing_email" type="email" defaultValue={String(data?.billing_email ?? '')} placeholder="Billing email"/><textarea className="min-h-28 rounded-md border border-[var(--border)] bg-[var(--surface)] p-3 sm:col-span-2" name="billing_address" defaultValue={String(data?.billing_address ?? '')} placeholder="Billing address"/><input className={fieldClass} name="payment_terms" defaultValue={String(data?.payment_terms ?? 'Due within 30 days')} placeholder="Payment terms"/><input className={fieldClass} name="default_currency" maxLength={3} defaultValue={String(data?.default_currency ?? 'ZAR')} placeholder="Currency (e.g. ZAR)"/><label className="grid gap-2 text-sm text-[var(--text-secondary)]">Invoice prefix<input className={fieldClass} name="invoice_prefix" defaultValue={String(data?.invoice_prefix ?? 'INV')} /></label><label className="grid gap-2 text-sm text-[var(--text-secondary)]">Next invoice number<input className={fieldClass} name="next_invoice_number" type="number" min="1" defaultValue={String(data?.next_invoice_number ?? 1)} /></label><label className="grid gap-2 text-sm text-[var(--text-secondary)]">Quote prefix<input className={fieldClass} name="quote_prefix" defaultValue={String(data?.quote_prefix ?? 'QUO')} /></label><label className="grid gap-2 text-sm text-[var(--text-secondary)]">Next quote number<input className={fieldClass} name="next_quote_number" type="number" min="1" defaultValue={String(data?.next_quote_number ?? 1)} /></label>{canManage && <button className={buttonClass}>Save company finance profile</button>}</form></Workspace>;
}


type EmployeeInvoice = {
  id: string;
  submission_number: string;
  employee_name: string;
  employee_email: string;
  status: string;
  invoice_date: string;
  currency: string;
  line_items: { description: string; quantity: string; unit_amount: string; line_total: string }[];
  total_amount: string;
  notes: string;
};
type EmployeeLine = { description: string; quantity: string; unit_amount: string };

export function EmployeeInvoicePage() {
  const organizationId = useOrganization();
  const canManage = useFinanceManage();
  const [items, setItems] = useState<EmployeeInvoice[]>([]);
  const [message, setMessage] = useState("");
  const [lines, setLines] = useState<EmployeeLine[]>([{ description: "", quantity: "1", unit_amount: "" }]);
  const load = useCallback(() => {
    if (!organizationId) return Promise.resolve();
    return apiRequest<EmployeeInvoice[]>(`/api/finance/employee-invoices/?organization_id=${organizationId}`).then(setItems);
  }, [organizationId]);
  useEffect(() => { void load().catch((error) => setMessage(error instanceof Error ? error.message : "Unable to load employee invoices.")); }, [load]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organizationId) return;
    const form = new FormData(event.currentTarget);
    try {
      await apiRequest("/api/finance/employee-invoices/", {
        method: "POST",
        body: JSON.stringify({
          organization_id: organizationId,
          invoice_date: form.get("invoice_date"),
          currency: form.get("currency"),
          line_items: lines,
          notes: form.get("notes") || "",
        }),
      });
      event.currentTarget.reset();
      setLines([{ description: "", quantity: "1", unit_amount: "" }]);
      setMessage("Employee invoice submitted to the finance team.");
      await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to submit employee invoice."); }
  }
  async function updateStatus(id: string, status: string) {
    try { await apiRequest(`/api/finance/employee-invoices/${id}/`, { method: "PATCH", body: JSON.stringify({ status }) }); await load(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Unable to update invoice status."); }
  }
  function downloadInvoice(item: EmployeeInvoice) {
    const rows = [["Submission", item.submission_number], ["Employee", item.employee_name || item.employee_email], ["Date", item.invoice_date], ["Currency", item.currency], [], ["Description", "Quantity", "Unit amount", "Line total"], ...item.line_items.map((line) => [line.description, line.quantity, line.unit_amount, line.line_total]), [], ["Total", item.total_amount]];
    const csv = rows.map((row) => row.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${item.submission_number}.csv`; anchor.click(); URL.revokeObjectURL(url);
  }
  return <Workspace>
    <PageHeader eyebrow="Finance / Internal invoices" title="Employee invoicing hub" description="Team members submit salary, commission, and reimbursable line items. Finance managers review and mark submissions settled." />
    <div className="mt-7 grid gap-6 xl:grid-cols-[24rem_minmax(0,1fr)]">
      <form className="evolve-panel grid content-start gap-4 p-5" onSubmit={submit}>
        <h2 className="font-semibold">Submit internal invoice</h2>
        <input className={fieldClass} name="invoice_date" type="date" required />
        <input className={fieldClass} name="currency" maxLength={3} defaultValue="ZAR" placeholder="Currency" required />
        <div className="grid gap-3"><p className="text-sm font-medium">Invoice lines</p>{lines.map((line, index) => <div className="grid gap-2 rounded-lg border border-[var(--border)] p-3 sm:grid-cols-[1fr_5rem_7rem_auto]" key={index}><input className={fieldClass} value={line.description} onChange={(event) => setLines((current) => current.map((item, position) => position === index ? { ...item, description: event.target.value } : item))} placeholder="Salary, commission, or reimbursement" required /><input className={fieldClass} value={line.quantity} onChange={(event) => setLines((current) => current.map((item, position) => position === index ? { ...item, quantity: event.target.value } : item))} type="number" min="0.001" step="0.001" placeholder="Qty" required /><input className={fieldClass} value={line.unit_amount} onChange={(event) => setLines((current) => current.map((item, position) => position === index ? { ...item, unit_amount: event.target.value } : item))} type="number" min="0" step="0.01" placeholder="Amount" required />{lines.length > 1 && <button className={secondaryButtonClass} type="button" onClick={() => setLines((current) => current.filter((_, position) => position !== index))}>Remove</button>}</div>)}<button className={secondaryButtonClass + " justify-self-start"} type="button" onClick={() => setLines((current) => [...current, { description: "", quantity: "1", unit_amount: "" }])}>Add invoice line</button></div>
        <textarea className="min-h-24 rounded-md border border-[var(--border)] bg-[var(--surface)] p-3" name="notes" placeholder="Notes for the finance team" />
        <button className={buttonClass}>Submit for review</button>
      </form>
      <section className="evolve-panel overflow-hidden">
        <div className="border-b border-[var(--border)] p-5"><h2 className="font-semibold">Submissions</h2><p className="mt-1 text-sm text-[var(--text-muted)]">{canManage ? "All team submissions" : "Your submissions only"}</p></div>
        <div>{items.map((item) => <div className="grid gap-3 border-b border-[var(--border)] p-5 sm:grid-cols-[1fr_auto_auto]" key={item.id}><div><p className="font-semibold">{item.submission_number}</p><p className="text-sm text-[var(--text-muted)]">{item.employee_name || item.employee_email} · {item.invoice_date}</p><p className="mt-2 text-sm">{item.line_items.map((line) => line.description).join(", ")}</p></div><StatusBadge positive={item.status === "settled" || item.status === "approved"}>{item.status}</StatusBadge><div className="text-right"><p className="font-semibold">{money(item.total_amount, item.currency)}</p><button className={secondaryButtonClass + " mt-2"} type="button" onClick={() => downloadInvoice(item)}>Download CSV</button>{canManage && <select className={fieldClass} value={item.status} onChange={(event) => void updateStatus(item.id, event.target.value)}><option value="submitted">Submitted</option><option value="review">Under review</option><option value="approved">Approved</option><option value="settled">Settled</option><option value="rejected">Rejected</option></select>}</div></div>)}{!items.length && <EmptyState title="No employee invoices" detail="Submit the first internal invoice for finance review." />}</div>
      </section>
    </div>
    {message && <p className="mt-4 text-sm text-[var(--accent-strong)]">{message}</p>}
  </Workspace>;
}


type Quote = { id: string; quote_number: string; status: string; billed_to_name: string; billed_to_email: string; currency: string; valid_until: string | null; subtotal: string; total_amount: string; notes: string; line_items: { description: string; quantity: string; unit_amount: string; line_total: string }[] };

export function QuoteWorkspacePage() {
  const organizationId = useOrganization();
  const canManage = useFinanceManage();
  const [items, setItems] = useState<Quote[]>([]);
  const [message, setMessage] = useState("");
  const load = useCallback(() => organizationId ? apiRequest<Quote[]>(`/api/finance/quotes/?organization_id=${organizationId}`).then(setItems) : Promise.resolve(), [organizationId]);
  useEffect(() => { void load().catch((error) => setMessage(error instanceof Error ? error.message : "Unable to load quotes.")); }, [load]);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organizationId) return;
    const form = new FormData(event.currentTarget);
    try {
      await apiRequest("/api/finance/quotes/", { method: "POST", body: JSON.stringify({
        organization_id: organizationId, billed_to_name: form.get("billed_to_name"), billed_to_email: form.get("billed_to_email"),
        currency: form.get("currency"), valid_until: form.get("valid_until") || null, tax_amount: form.get("tax_amount") || "0", notes: form.get("notes") || "",
        line_items: [{ description: form.get("description"), quantity: form.get("quantity") || "1", unit_amount: form.get("unit_amount") }],
      })});
      event.currentTarget.reset(); setMessage("Quote created."); await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to create quote."); }
  }
  return <Workspace><PageHeader eyebrow="Finance / Quotes" title="Quotes" description="Create and track promoter quotes using the configured company billing profile and sequential quote numbers." />
    <div className="mt-7 grid gap-6 xl:grid-cols-[24rem_minmax(0,1fr)]">
      {canManage && <form className="evolve-panel grid content-start gap-4 p-5" onSubmit={create}><h2 className="font-semibold">New quote</h2><input className={fieldClass} name="billed_to_name" placeholder="Promoter or client" required/><input className={fieldClass} name="billed_to_email" type="email" placeholder="Client email"/><div className="grid grid-cols-2 gap-3"><input className={fieldClass} name="currency" defaultValue="ZAR" maxLength={3} required/><input className={fieldClass} name="valid_until" type="date"/></div><input className={fieldClass} name="description" placeholder="Line item description" required/><div className="grid grid-cols-2 gap-3"><input className={fieldClass} name="quantity" type="number" min="0.001" step="0.001" defaultValue="1" required/><input className={fieldClass} name="unit_amount" type="number" min="0" step="0.01" placeholder="Amount" required/></div><input className={fieldClass} name="tax_amount" type="number" min="0" step="0.01" defaultValue="0" placeholder="Tax"/><textarea className="min-h-24 rounded-md border border-[var(--border)] bg-[var(--surface)] p-3" name="notes" placeholder="Quote notes"/><button className={buttonClass}>Create quote</button></form>}
      <section className="evolve-panel overflow-hidden"><div className="border-b border-[var(--border)] p-5"><h2 className="font-semibold">Quote register</h2></div><div>{items.map((item) => <div className="grid gap-3 border-b border-[var(--border)] p-5 sm:grid-cols-[1fr_auto_auto]" key={item.id}><div><p className="font-semibold">{item.quote_number}</p><p className="text-sm text-[var(--text-muted)]">{item.billed_to_name} · Valid until {item.valid_until || "not set"}</p><p className="mt-2 text-sm">{item.line_items.map((line) => line.description).join(", ")}</p></div><StatusBadge positive={item.status === "accepted"}>{item.status}</StatusBadge><strong>{money(item.total_amount, item.currency)}</strong></div>)}{!items.length && <EmptyState title="No quotes" detail="Create the first quote from this finance workspace." />}</div></section>
    </div>{message && <p className="mt-4 text-sm text-[var(--accent-strong)]">{message}</p>}</Workspace>;
}
