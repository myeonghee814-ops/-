import type { BatterySnapshot } from "../api/types";

export default function BatterySnapshotView({ snapshot }: { snapshot: BatterySnapshot }) {
  const fields: [string, string][] = [
    ["양극", snapshot.cathode],
    ["음극", snapshot.anode],
    ["전해액", snapshot.electrolyte],
    ["전압 범위", snapshot.voltage_window],
    ["셀 종류", snapshot.cell_type],
  ];

  return (
    <div className="battery-snapshot">
      {fields.map(([label, value]) => (
        <div className="battery-snapshot-field" key={label}>
          <span className="battery-snapshot-label">{label}</span>
          <span className="battery-snapshot-value">{value || "정보 없음"}</span>
        </div>
      ))}
    </div>
  );
}
