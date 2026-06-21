import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import type { AuthState } from "@/types";

function initials(auth: AuthState | null): string {
  const source = auth?.name || auth?.email || "Google";
  return source
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "G";
}

export function AccountChip({ auth }: { auth: AuthState | null }) {
  if (!auth?.signed_in) return null;

  return (
    <Badge variant="secondary" className="w-fit gap-2 rounded-full py-1 pr-3 pl-1">
      <Avatar className="size-6">
        <AvatarImage src={auth.picture ?? undefined} alt={auth.name ?? auth.email ?? "Conta Google"} />
        <AvatarFallback>{initials(auth)}</AvatarFallback>
      </Avatar>
      <span className="truncate">{auth.email ?? auth.name ?? "Conta Google conectada"}</span>
    </Badge>
  );
}
