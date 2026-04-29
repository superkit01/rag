import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-pulse rounded",
        className
      )}
      style={{ background: "var(--line)" }}
    />
  );
}

export function DocumentSkeleton() {
  return (
    <div className="p-4 border rounded-lg bg-white space-y-3">
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-3 w-1/2" />
      <Skeleton className="h-3 w-1/3" />
    </div>
  );
}

export function ChatMessageSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-6 w-32" />
      <Skeleton className="h-20 w-full rounded-2xl" />
    </div>
  );
}
