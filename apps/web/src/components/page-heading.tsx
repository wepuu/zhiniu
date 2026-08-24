export function PageHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <header className="border-ink/10 border-b pb-6">
      <p className="text-blue text-xs font-medium">{eyebrow}</p>
      <h1 className="font-display mt-2 text-3xl font-semibold tracking-tight">
        {title}
      </h1>
      <p className="text-slate mt-2 max-w-2xl text-sm leading-6">
        {description}
      </p>
    </header>
  );
}
