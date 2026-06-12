import { AppIcon } from "../icons";

export function OfflinePill() {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex max-w-xs items-center gap-2 rounded-full border border-warning/30 bg-background px-3 py-2 text-xs text-foreground shadow-lg">
      <AppIcon name="alertCircle" />
      <span>sem conexão com o servidor - dados podem estar desatualizados</span>
    </div>
  );
}
