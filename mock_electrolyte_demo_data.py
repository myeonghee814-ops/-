"""
[MOCK / DEMO DATA ONLY]

This script does NOT query PubMed or any real database. The `papers_data`
list below is AI-generated example content — titles, author names, and
abstracts are invented to illustrate the shape of a research report and
must not be treated as real publications or cited as such.

For an actual literature search, use `pubmed_electrolyte_scraper.py`,
which queries the real PubMed E-utilities API.
"""

import pandas as pd

SEARCH_KEYWORD = "(lithium battery electrolyte additive) AND (SEI OR 'high temperature' OR 'cycling stability')"
OUTPUT_FILENAME = "electrolyte_MOCK_DEMO_not_real_papers.xlsx"
SOURCE_LABEL = "SYNTHETIC EXAMPLE (AI-generated, not a real paper)"

# AI-generated example entries illustrating common electrolyte-additive
# research themes. Titles/authors/abstracts are fabricated for demo
# purposes only and do not correspond to verified real publications.
papers_data = [
    {
        "chemical_name": "Prop-1-ene-1,3-sultone (PST)",
        "target_issue": "High-temperature gas evolution and swelling in pouch cells",
        "mechanism_summary": "Sacrificial oxidation forms a sulfur-rich, robust passivation SEI layer on the cathode surface, effectively preventing direct contact and continuous decomposition of the linear carbonate solvents.",
        "title": "Synergistic Effect of Prop-1-ene-1,3-sultone as an Electrolyte Additive for High-Voltage Lithium-Ion Batteries",
        "authors": "Kim, H., Lee, S., Mun, J.",
        "abstract": "High-voltage operation of lithium-ion batteries often triggers severe electrolyte decomposition and gas evolution at elevated temperatures. In this study, we investigate Prop-1-ene-1,3-sultone (PST) as a functional electrolyte additive. Electrochemical evaluations demonstrate that PST undergoes preferential decomposition to form a robust cathode-electrolyte interphase (CEI), significantly reducing gassing and boosting cycling stability at 45°C."
    },
    {
        "chemical_name": "Lithium difluorophosphate (LiDFP)",
        "target_issue": "Slow Li-ion desolvation kinetics and poor fast-charging performance",
        "mechanism_summary": "Lowers the activation energy of the Li-ion desolvation process at the interface by incorporating stable, ionic-conductive F and P species into the anode SEI film.",
        "title": "Lithium Difluorophosphate as a Highly Effective Additive for Fast-Charging Cylindrical Cells",
        "authors": "Wang, L., Zhang, Y., Kumar, P.",
        "abstract": "Fast charging typically induces lithium plating on graphite anodes. Herein, lithium difluorophosphate (LiDFP) is introduced to modulate the solvation structure. Due to its high ionic conductivity, the LiDFP-derived SEI facilitates rapid charge-transfer kinetics, achieving 80% capacity retention under 3C fast-charging conditions over 500 cycles."
    },
    {
        "chemical_name": "Fluoroethylene carbonate (FEC)",
        "target_issue": "Severe volume expansion and mechanical cracking of silicon-based anodes",
        "mechanism_summary": "Forms a highly flexible, poly(FEC)-based polymeric SEI matrix containing fine LiF particles, successfully accommodating the large stress variations of silicon during lithiation.",
        "title": "Tailoring the Polymeric SEI Film via Fluoroethylene Carbonate for High-Capacity Silicon-Graphite Anodes",
        "authors": "Doñoro, Á., Etacheri, V., Choi, J.",
        "abstract": "Silicon anodes suffer from immense volume expansion (~300%). Fluoroethylene carbonate (FEC) is widely applied to solve this mechanical degradation. The in-situ formed flexible polymeric framework prevents structural pulverization, maintaining an initial coulombic efficiency above 92%."
    },
    {
        "chemical_name": "Tris(trimethylsily) phosphite (TMSPi)",
        "target_issue": "HF attack and transition metal (Co/Mn) dissolution under high-voltage (4.5V+)",
        "mechanism_summary": "The silyl groups efficiently scavenge trace moisture and harmful HF in the bulk electrolyte, shielding the transition metal oxides on the cathode from structural dissolution.",
        "title": "HF-Scavenging Mechanism of Tris(trimethylsilyl) Phosphite Additive in High-Voltage LiNi0.8Co0.1Mn0.1O2 Cathodes",
        "authors": "Jia, M., Wu, C., Ming, J.",
        "abstract": "Trace moisture in LiPF6-based electrolytes inevitably generates corrosive HF acid, which severely damages the cathode interface. TMSPi exhibits exceptional scavenging capabilities toward HF. Cells with 1.0 wt% TMSPi showed minimal cobalt/nickel dissolution and maintained a stable crystal structure up to 4.5V."
    },
    {
        "chemical_name": "Succinonitrile (SN)",
        "target_issue": "Thermal instability and electrolyte oxidation at high temperatures (60°C+)",
        "mechanism_summary": "Forms strong coordinate bonds between its nitrile (-C≡N) functional groups and surface copper/transition metals, forming a protective complex layer that inhibits catalytic oxidation.",
        "title": "Nitrile-Based Electrolyte Additive for Suppressing Catalytic Decomposition at High Temperatures",
        "authors": "Zhang, J., Zhou, M., Zheng, J.",
        "abstract": "Succinonitrile (SN) is evaluated as a thermal stabilizer. The strong binding energy between SN and metal active sites creates a deactivated layer, suppressing transition metal-catalyzed electrolyte oxidation at 60°C and dramatically extending the storage life of pouch cells."
    },
    {
        "chemical_name": "Lithium difluoro(oxalato)borate (LiDFOB)",
        "target_issue": "Imbalanced anode/cathode interfacial passivation in Lithium Metal Batteries",
        "mechanism_summary": "Undergoes hybrid decomposition to simultaneously form a rigid B-O-rich CEI on the cathode and a stable LiF-rich SEI on the lithium metal anode, ensuring balanced dual-interfacial protection.",
        "title": "Dual-Interfacial Stabilization via Lithium Difluoro(oxalato)borate for 5V Lithium Metal Batteries",
        "authors": "Yao, S., Xu, J., Jiang, Y.",
        "abstract": "Lithium metal anodes exhibit severe dendrite growth and low coulombic efficiency. LiDFOB combines the structural advantages of LiBOB and LiFOB. It regulates the flux of lithium ions, establishing a highly uniform, low-impedance interphase that achieves dendrite-free cycling over 400 hours."
    },
    {
        "chemical_name": "Vinylene carbonate (VC)",
        "target_issue": "Continuous electrolyte consumption on graphite during initial formation cycle",
        "mechanism_summary": "Polymerizes via radical mechanisms at the graphite surface prior to carbonate solvent reduction, creating a dense, thin organic SEI that effectively blocks electron tunneling.",
        "title": "Radical Polymerization Mechanisms of Vinylene Carbonate on Graphite Surfaces Revisited",
        "authors": "Kim, YU., Sung, JY., Lee, JN.",
        "abstract": "Vinylene carbonate (VC) remains a benchmark additive for forming a reliable SEI on graphite. This study tracks the real-time formation kinetics of poly(VC). The continuous coating blocks electron transfer while maintaining high lithium-ion permeability, enhancing long-term capacity retention."
    },
    {
        "chemical_name": "1,3-Propane sultone (1,3-PS)",
        "target_issue": "Poor safety and impedance rise at low temperatures",
        "mechanism_summary": "Optimizes the thickness of the sulfur-rich interphase to decrease the interfacial impedance, improving low-temperature desolvation kinetics without sacrificing high-temperature safety.",
        "title": "Balancing High-Temperature Safety and Low-Temperature Power via 1,3-Propane Sultone Additives",
        "authors": "Lee, D., Lim, S., Woo, S.",
        "abstract": "Sultone additives are notorious for increasing low-temperature impedance. However, optimizing the concentration of 1,3-PS to 0.5 wt% reveals a balanced profile. The resulting thin film offers structural security against thermal runaway while reducing charge-transfer resistance at -20°C."
    },
    {
        "chemical_name": "Ethylene sulfate (DTD)",
        "target_issue": "Initial capacity loss (Irreversible capacity) during formation",
        "mechanism_summary": "Reduces at a higher potential than EC to form a highly uniform sulfate-containing inorganic SEI, minimizing initial lithium consumption and improving Coulombic Efficiency.",
        "title": "Suppression of Irreversible Capacity Loss in Lithium-Ion Batteries using Ethylene Sulfate Additive",
        "authors": "Zou, Y., Lv, H., Wu, X.",
        "abstract": "Ethylene sulfate (DTD) is investigated to reduce the initial irreversible capacity during the first cycle. Characterizations show that DTD significantly suppresses co-intercalation of solvents into graphite layers, increasing the first-cycle coulombic efficiency from 86.5% to 91.2%."
    },
    {
        "chemical_name": "Adiponitrile (ADN)",
        "target_issue": "Voltage instability and metal dissolution in Nickel-Rich Cathodes (NMC 811)",
        "mechanism_summary": "The dinitrile structure offers excellent electrochemical stability at high oxidation potentials, forming a robust complex with surface nickel atoms to block solvent oxidation pathways.",
        "title": "Stabilizing Nickel-Rich NMC 811 Cathodes up to 4.6V with Adiponitrile Electrolyte Additive",
        "authors": "Shen, N., Wang, L., Dai, D.",
        "abstract": "Nickel-rich NMC cathodes suffer from surface structural reconstruction at ultra-high voltages. Adiponitrile (ADN) possesses a wide electrochemical window. It effectively coordinates with unsaturated Ni3+/Ni4+ ions, preventing phase transitions and stabilizing the electrode-electrolyte interface."
    },
]

def main():
    print("=" * 70)
    print("[MOCK / DEMO DATA] The rows below are AI-generated example content,")
    print("NOT results from a real PubMed search. Do not cite as real papers.")
    print("=" * 70)
    print(f"참고 키워드(실 검색 아님): [{SEARCH_KEYWORD}]")

    df = pd.DataFrame(papers_data)
    df["source"] = SOURCE_LABEL

    cols = ["source", "chemical_name", "target_issue", "mechanism_summary", "title", "authors", "abstract"]
    df = df[cols]

    df.to_excel(OUTPUT_FILENAME, index=False, engine="openpyxl")
    print(f"\n[DONE] Wrote {len(df)} synthetic example rows to '{OUTPUT_FILENAME}'.")
    print("Reminder: this file contains fabricated demo data, not verified literature.")

if __name__ == "__main__":
    main()
