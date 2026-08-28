"use client";

import { useEffect, useRef, useState } from "react";

import { buttonClass, secondaryButtonClass } from "@/components/ui/page";

type ConfirmationOptions = {
  title: string;
  description: string;
  entityName?: string;
  confirmLabel?: string;
  destructive?: boolean;
  reasonLabel?: string;
  reasonRequired?: boolean;
};

export function confirmAction(message: string, confirmLabel = "Confirm"): Promise<boolean> {
  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    dialog.className = "w-[calc(100%-2rem)] max-w-md rounded-md border border-neutral-700 bg-neutral-950 p-6 text-neutral-100 shadow-2xl backdrop:bg-black/70";
    dialog.setAttribute("aria-labelledby", "confirmation-title");

    const title = document.createElement("h2");
    title.id = "confirmation-title";
    title.className = "text-lg font-semibold";
    title.textContent = "Confirm action";
    const description = document.createElement("p");
    description.className = "mt-3 text-sm leading-6 text-neutral-400";
    description.textContent = message;
    const actions = document.createElement("div");
    actions.className = "mt-6 flex justify-end gap-3";
    const cancel = document.createElement("button");
    cancel.className = secondaryButtonClass;
    cancel.textContent = "Cancel";
    const submit = document.createElement("button");
    submit.className = buttonClass;
    submit.textContent = confirmLabel;
    actions.append(cancel, submit);
    dialog.append(title, description, actions);
    document.body.append(dialog);

    const finish = (answer: boolean) => {
      dialog.close();
      dialog.remove();
      resolve(answer);
    };
    cancel.addEventListener("click", () => finish(false));
    submit.addEventListener("click", () => finish(true));
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      finish(false);
    });
    dialog.showModal();
    cancel.focus();
  });
}

export function promptAction(message: string, initialValue = ""): Promise<string | null> {
  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    dialog.className = "w-[calc(100%-2rem)] max-w-md rounded-md border border-neutral-700 bg-neutral-950 p-6 text-neutral-100 shadow-2xl backdrop:bg-black/70";
    const label = document.createElement("label");
    label.className = "grid gap-3 text-sm text-neutral-300";
    label.textContent = message;
    const input = document.createElement("textarea");
    input.className = "min-h-24 rounded-md border border-neutral-700 bg-neutral-900 p-3 outline-none focus:border-amber-400";
    input.value = initialValue;
    const actions = document.createElement("div");
    actions.className = "mt-6 flex justify-end gap-3";
    const cancel = document.createElement("button");
    cancel.className = secondaryButtonClass;
    cancel.textContent = "Cancel";
    const submit = document.createElement("button");
    submit.className = buttonClass;
    submit.textContent = "Continue";
    label.append(input);
    actions.append(cancel, submit);
    dialog.append(label, actions);
    document.body.append(dialog);
    const finish = (answer: string | null) => {
      dialog.close();
      dialog.remove();
      resolve(answer);
    };
    cancel.addEventListener("click", () => finish(null));
    submit.addEventListener("click", () => finish(input.value.trim()));
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      finish(null);
    });
    dialog.showModal();
    input.focus();
    input.select();
  });
}

type PendingConfirmation = ConfirmationOptions & {
  resolve: (value: string | boolean) => void;
};

export function useActionConfirmation() {
  const [pending, setPending] = useState<PendingConfirmation | null>(null);
  const [reason, setReason] = useState("");
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (pending) confirmRef.current?.focus();
  }, [pending]);

  function confirm(options: ConfirmationOptions): Promise<string | boolean> {
    return new Promise((resolve) => {
      setReason("");
      setPending({ ...options, resolve });
    });
  }

  function close(value: string | boolean) {
    pending?.resolve(value);
    setPending(null);
    setReason("");
  }

  const dialog = pending ? (
    <div
      aria-labelledby="action-dialog-title"
      aria-describedby="action-dialog-description"
      aria-modal="true"
      className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4"
      onKeyDown={(event) => {
        if (event.key === "Escape") close(false);
      }}
      role="dialog"
    >
      <div className="w-full max-w-md rounded-md border border-neutral-700 bg-neutral-950 p-6 shadow-2xl">
        <h2 className="text-lg font-semibold" id="action-dialog-title">
          {pending.title}
        </h2>
        <p className="mt-3 text-sm leading-6 text-neutral-400" id="action-dialog-description">
          {pending.description}
        </p>
        {pending.entityName && (
          <p className="mt-3 break-words rounded-md bg-neutral-900 px-3 py-2 text-sm font-medium">
            {pending.entityName}
          </p>
        )}
        {pending.reasonLabel && (
          <label className="mt-5 grid gap-2 text-sm text-neutral-300">
            {pending.reasonLabel}
            <textarea
              autoFocus
              className="min-h-24 rounded-md border border-neutral-700 bg-neutral-900 p-3 outline-none focus:border-amber-400"
              onChange={(event) => setReason(event.target.value)}
              required={pending.reasonRequired}
              value={reason}
            />
          </label>
        )}
        <div className="mt-6 flex justify-end gap-3">
          <button className={secondaryButtonClass} onClick={() => close(false)} type="button">
            Cancel
          </button>
          <button
            className={pending.destructive ? "inline-flex h-10 items-center rounded-md bg-red-700 px-4 text-sm font-semibold text-white hover:bg-red-600 disabled:opacity-50" : buttonClass}
            disabled={pending.reasonRequired && !reason.trim()}
            onClick={() => close(pending.reasonLabel ? reason.trim() : true)}
            ref={confirmRef}
            type="button"
          >
            {pending.confirmLabel ?? "Confirm"}
          </button>
        </div>
      </div>
    </div>
  ) : null;

  return { confirm, dialog };
}
