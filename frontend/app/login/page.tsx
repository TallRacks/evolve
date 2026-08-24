import Link from "next/link";

export default function LoginPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-zinc-100 px-6 text-zinc-950">
      <section className="w-full max-w-md border border-zinc-200 bg-white p-8">
        <p className="text-sm font-medium uppercase text-emerald-700">Private access</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal">Sign in to Evolve v2</h1>
        <p className="mt-4 leading-7 text-zinc-600">
          Session sign-in will be connected to Django in the next authentication workflow.
        </p>
        <Link
          className="mt-8 inline-flex h-10 items-center bg-zinc-950 px-4 text-sm font-medium text-white"
          href="/dashboard"
        >
          Continue to portal shell
        </Link>
      </section>
    </main>
  );
}
