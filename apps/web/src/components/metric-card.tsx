import { Card } from "./ui/card";

export function MetricCard({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note: string;
}) {
  return (
    <Card className="p-4">
      <p className="text-slate text-xs uppercase tracking-[0.16em]">{label}</p>
      <p className="font-data mt-3 text-2xl font-semibold tracking-tight">
        {value}
      </p>
      <p className="text-slate mt-1 text-xs">{note}</p>
    </Card>
  );
}
