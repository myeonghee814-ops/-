import type { BatterySnapshot } from "../api/types";

export default function BatterySnapshotView({ snapshot }: { snapshot: BatterySnapshot }) {
  const fields: [string, string][] = [
    ["Cathode", snapshot.cathode],
    ["Anode", snapshot.anode],
    ["Electrolyte", snapshot.electrolyte],
    ["Voltage Window", snapshot.voltage_window],
    ["Cell Type", snapshot.cell_type],
  ];

  return (
    <div className="battery-snapshot">
      {fields.map(([label, value]) => (
        <div className="battery-snapshot-field" key={label}>
          <span className="battery-snapshot-label">{label}</span>
          <span className="battery-snapshot-value">{value || "Not specified"}</span>
        </div>
      ))}
    </div>
  );
}
