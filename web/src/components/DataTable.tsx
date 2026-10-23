export function DataTable({ columns, rows }: { columns: string[]; rows: (string | number | boolean | null)[][] }) {
  const fmt = (v: string | number | boolean | null) =>
    typeof v === "number" ? v.toLocaleString("fr-FR", { maximumFractionDigits: 3 }) : String(v ?? "");
  const numeric = columns.map((_, j) => rows.some((r) => typeof r[j] === "number"));
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c, j) => (
              <th key={c} className={numeric[j] ? "num" : ""}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 15).map((row, i) => (
            <tr key={i}>
              {row.map((v, j) => (
                <td key={j} className={typeof v === "number" ? "num" : ""}>
                  {fmt(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 15 && <p className="muted small">{rows.length - 15} lignes supplémentaires dans le rapport JSON.</p>}
    </div>
  );
}
