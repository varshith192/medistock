"""Synthetic but realistic pharmacy inventory dataset (operational data only — no patient data)."""
from __future__ import annotations

SUPPLIERS = [
    # id, name, legal name, city, contracted lead days, MOQ, email, phone
    ("SUP-A", "Supplier A", "Meridian Pharma Distributors Pvt Ltd", "Hyderabad", 2.0, 50, "orders@meridianpharma.example", "+91 40 4012 7780"),
    ("SUP-B", "Supplier B", "Carewell Pharma Supply LLP", "Hyderabad", 2.0, 50, "dispatch@carewell.example", "+91 40 4431 2290"),
    ("SUP-C", "Supplier C", "Lifeline Medisales", "Secunderabad", 3.0, 100, "sales@lifelinemedi.example", "+91 40 2780 5561"),
    ("SUP-D", "Supplier D", "Nova Coldchain Logistics", "Bengaluru", 2.0, 20, "coldchain@novalogistics.example", "+91 80 4120 9934"),
    ("SUP-E", "Supplier E", "Sterling Biologics Distribution", "Hyderabad", 1.0, 10, "urgent@sterlingbio.example", "+91 40 6619 0045"),
    ("SUP-F", "Supplier F", "Trident Generics Wholesale", "Vijayawada", 4.0, 200, "po@tridentgenerics.example", "+91 866 247 3310"),
]

# Delivery behaviour used only to synthesise historical order records.
# (mean multiplier on contracted lead time, spread)
SUPPLIER_PROFILE = {
    "SUP-A": (1.12, 0.12),
    "SUP-B": (0.86, 0.08),
    "SUP-C": (1.06, 0.12),
    "SUP-D": (1.45, 0.30),
    "SUP-E": (1.00, 0.10),
    "SUP-F": (1.08, 0.10),
}
# Supplier A has allocation problems specifically on antibiotics.
SUPPLIER_A_ANTIBIOTIC_PROFILE = (1.65, 0.25)

# id, name, generic, form, category, stock, daily demand, pack, unit cost (INR),
# days to expiry, storage, primary supplier, approved suppliers, essential
MEDICINES = [
    ("MED-001", "Amoxicillin 500mg", "Amoxicillin", "Capsule", "Antibiotics", 42, 15, 50, 4.2, 120, "Room temperature", "SUP-A", ["SUP-A", "SUP-B", "SUP-C"], 1),
    ("MED-002", "Paracetamol 500mg", "Paracetamol", "Tablet", "Analgesics", 280, 20, 100, 0.9, 240, "Room temperature", "SUP-B", ["SUP-B", "SUP-A", "SUP-F"], 1),
    ("MED-003", "Azithromycin 500mg", "Azithromycin", "Tablet", "Antibiotics", 35, 7, 30, 18.5, 90, "Room temperature", "SUP-B", ["SUP-B", "SUP-A"], 1),
    ("MED-004", "Salbutamol Inhaler 100mcg", "Salbutamol", "Inhaler", "Respiratory", 14, 8, 10, 142.0, 310, "Room temperature", "SUP-C", ["SUP-C", "SUP-B"], 1),
    ("MED-005", "Insulin Glargine 100IU/ml", "Insulin glargine", "Pen", "Antidiabetics", 9, 6, 5, 690.0, 150, "Cold chain 2-8°C", "SUP-D", ["SUP-D", "SUP-E"], 1),
    ("MED-006", "ORS Sachet 21g", "Oral rehydration salts", "Sachet", "Gastrointestinal", 70, 38, 100, 6.5, 400, "Room temperature", "SUP-C", ["SUP-C", "SUP-F"], 1),
    ("MED-007", "Ceftriaxone 1g Injection", "Ceftriaxone", "Vial", "Antibiotics", 18, 6, 10, 48.0, 210, "Room temperature", "SUP-A", ["SUP-A", "SUP-B"], 1),
    ("MED-008", "Pantoprazole 40mg", "Pantoprazole", "Tablet", "Gastrointestinal", 95, 28, 100, 2.1, 380, "Room temperature", "SUP-F", ["SUP-F", "SUP-B"], 0),
    ("MED-009", "Montelukast 10mg", "Montelukast", "Tablet", "Respiratory", 40, 11, 30, 7.8, 260, "Room temperature", "SUP-B", ["SUP-B", "SUP-C"], 0),
    ("MED-010", "Enoxaparin 40mg Injection", "Enoxaparin", "Prefilled syringe", "Anticoagulants", 11, 3, 10, 355.0, 180, "Cold chain 2-8°C", "SUP-D", ["SUP-D", "SUP-E"], 1),
    ("MED-011", "Metformin 500mg", "Metformin", "Tablet", "Antidiabetics", 260, 48, 100, 1.1, 300, "Room temperature", "SUP-A", ["SUP-A", "SUP-F"], 1),
    ("MED-012", "Cetirizine 10mg", "Cetirizine", "Tablet", "Antihistamines", 130, 22, 100, 0.8, 420, "Room temperature", "SUP-C", ["SUP-C", "SUP-F"], 0),
    ("MED-013", "Ondansetron 4mg", "Ondansetron", "Tablet", "Gastrointestinal", 60, 9, 30, 4.6, 330, "Room temperature", "SUP-B", ["SUP-B", "SUP-C"], 0),
    ("MED-014", "Prednisolone 5mg", "Prednisolone", "Tablet", "Corticosteroids", 75, 12, 100, 0.7, 290, "Room temperature", "SUP-C", ["SUP-C", "SUP-B"], 1),
    ("MED-015", "Doxycycline 100mg", "Doxycycline", "Capsule", "Antibiotics", 48, 8, 50, 3.4, 200, "Room temperature", "SUP-A", ["SUP-A", "SUP-C"], 0),
    ("MED-016", "Ciprofloxacin 500mg", "Ciprofloxacin", "Tablet", "Antibiotics", 66, 10, 50, 3.9, 240, "Room temperature", "SUP-A", ["SUP-A", "SUP-C"], 0),
    ("MED-017", "Paracetamol 650mg", "Paracetamol", "Tablet", "Analgesics", 520, 34, 100, 1.3, 360, "Room temperature", "SUP-B", ["SUP-B", "SUP-F"], 1),
    ("MED-018", "Ibuprofen 400mg", "Ibuprofen", "Tablet", "Analgesics", 210, 14, 100, 1.2, 280, "Room temperature", "SUP-C", ["SUP-C", "SUP-F"], 0),
    ("MED-019", "Diclofenac 50mg", "Diclofenac", "Tablet", "Analgesics", 180, 9, 100, 0.9, 330, "Room temperature", "SUP-F", ["SUP-F", "SUP-C"], 0),
    ("MED-020", "Atorvastatin 10mg", "Atorvastatin", "Tablet", "Cardiovascular", 340, 19, 100, 2.4, 410, "Room temperature", "SUP-A", ["SUP-A", "SUP-B"], 1),
    ("MED-021", "Rosuvastatin 10mg", "Rosuvastatin", "Tablet", "Cardiovascular", 150, 8, 30, 5.2, 390, "Room temperature", "SUP-B", ["SUP-B", "SUP-A"], 0),
    ("MED-022", "Amlodipine 5mg", "Amlodipine", "Tablet", "Cardiovascular", 400, 26, 100, 0.8, 450, "Room temperature", "SUP-A", ["SUP-A", "SUP-F"], 1),
    ("MED-023", "Telmisartan 40mg", "Telmisartan", "Tablet", "Cardiovascular", 310, 18, 100, 2.9, 370, "Room temperature", "SUP-F", ["SUP-F", "SUP-A"], 1),
    ("MED-024", "Losartan 50mg", "Losartan", "Tablet", "Cardiovascular", 190, 11, 100, 2.2, 340, "Room temperature", "SUP-A", ["SUP-A", "SUP-B"], 1),
    ("MED-025", "Metoprolol 50mg", "Metoprolol", "Tablet", "Cardiovascular", 160, 9, 100, 3.1, 300, "Room temperature", "SUP-C", ["SUP-C", "SUP-A"], 1),
    ("MED-026", "Clopidogrel 75mg", "Clopidogrel", "Tablet", "Cardiovascular", 140, 7, 30, 3.6, 280, "Room temperature", "SUP-B", ["SUP-B", "SUP-A"], 1),
    ("MED-027", "Aspirin 75mg", "Acetylsalicylic acid", "Tablet", "Cardiovascular", 420, 21, 100, 0.4, 500, "Room temperature", "SUP-F", ["SUP-F", "SUP-C"], 1),
    ("MED-028", "Levothyroxine 50mcg", "Levothyroxine", "Tablet", "Endocrine", 260, 12, 100, 1.4, 320, "Room temperature", "SUP-B", ["SUP-B", "SUP-C"], 1),
    ("MED-029", "Glimepiride 2mg", "Glimepiride", "Tablet", "Antidiabetics", 180, 10, 100, 1.9, 350, "Room temperature", "SUP-A", ["SUP-A", "SUP-F"], 0),
    ("MED-030", "Sitagliptin 50mg", "Sitagliptin", "Tablet", "Antidiabetics", 90, 5, 30, 14.5, 300, "Room temperature", "SUP-B", ["SUP-B", "SUP-A"], 0),
    ("MED-031", "Omeprazole 20mg", "Omeprazole", "Capsule", "Gastrointestinal", 220, 15, 100, 1.0, 310, "Room temperature", "SUP-F", ["SUP-F", "SUP-B"], 0),
    ("MED-032", "Famotidine 20mg", "Famotidine", "Tablet", "Gastrointestinal", 120, 6, 100, 1.1, 290, "Room temperature", "SUP-C", ["SUP-C", "SUP-F"], 0),
    ("MED-033", "Domperidone 10mg", "Domperidone", "Tablet", "Gastrointestinal", 110, 7, 100, 0.9, 260, "Room temperature", "SUP-C", ["SUP-C", "SUP-F"], 0),
    ("MED-034", "Levocetirizine 5mg", "Levocetirizine", "Tablet", "Antihistamines", 150, 9, 100, 1.0, 340, "Room temperature", "SUP-C", ["SUP-C", "SUP-B"], 0),
    ("MED-035", "Budesonide Inhaler 200mcg", "Budesonide", "Inhaler", "Respiratory", 28, 2, 10, 310.0, 280, "Room temperature", "SUP-C", ["SUP-C", "SUP-B"], 1),
    ("MED-036", "Cefixime 200mg", "Cefixime", "Tablet", "Antibiotics", 320, 6, 100, 9.8, 38, "Room temperature", "SUP-C", ["SUP-C", "SUP-A"], 0),
    ("MED-037", "Metronidazole 400mg", "Metronidazole", "Tablet", "Antibiotics", 130, 8, 100, 0.8, 270, "Room temperature", "SUP-F", ["SUP-F", "SUP-C"], 1),
    ("MED-038", "Fluconazole 150mg", "Fluconazole", "Tablet", "Antifungals", 60, 3, 30, 6.2, 300, "Room temperature", "SUP-B", ["SUP-B", "SUP-C"], 0),
    ("MED-039", "Albendazole 400mg", "Albendazole", "Tablet", "Anthelmintics", 110, 2, 50, 3.5, 45, "Room temperature", "SUP-F", ["SUP-F", "SUP-C"], 0),
    ("MED-040", "Vitamin D3 60000 IU", "Cholecalciferol", "Capsule", "Vitamins & Supplements", 150, 4, 50, 11.0, 52, "Room temperature", "SUP-F", ["SUP-F", "SUP-B"], 0),
    ("MED-041", "Calcium + Vitamin D3", "Calcium carbonate / cholecalciferol", "Tablet", "Vitamins & Supplements", 300, 12, 100, 2.6, 420, "Room temperature", "SUP-F", ["SUP-F", "SUP-C"], 0),
    ("MED-042", "Ferrous Ascorbate + Folic Acid", "Ferrous ascorbate / folic acid", "Tablet", "Vitamins & Supplements", 240, 10, 100, 3.3, 380, "Room temperature", "SUP-F", ["SUP-F", "SUP-B"], 1),
    ("MED-043", "Dexamethasone 4mg Injection", "Dexamethasone", "Ampoule", "Corticosteroids", 110, 3, 25, 9.5, 28, "Room temperature", "SUP-A", ["SUP-A", "SUP-C"], 1),
    ("MED-044", "Normal Saline 0.9% 500ml", "Sodium chloride", "IV bottle", "IV Fluids", 120, 9, 24, 28.0, 520, "Room temperature", "SUP-C", ["SUP-C", "SUP-F"], 1),
    ("MED-045", "Povidone-Iodine 5% Solution", "Povidone-iodine", "Bottle", "Antiseptics", 90, 1.5, 12, 64.0, 55, "Room temperature", "SUP-F", ["SUP-F", "SUP-C"], 0),
    ("MED-046", "Hydroxychloroquine 200mg", "Hydroxychloroquine", "Tablet", "Immunology", 140, 3, 30, 7.4, 33, "Room temperature", "SUP-B", ["SUP-B", "SUP-C"], 0),
    ("MED-047", "Insulin Regular 40IU/ml", "Human insulin", "Vial", "Antidiabetics", 70, 2.5, 5, 155.0, 20, "Cold chain 2-8°C", "SUP-D", ["SUP-D", "SUP-E"], 1),
    ("MED-048", "Levofloxacin 500mg", "Levofloxacin", "Tablet", "Antibiotics", 85, 6, 50, 5.1, 230, "Room temperature", "SUP-C", ["SUP-C", "SUP-A"], 0),
]

# Recent demand spikes: medicine id -> (days since spike started, multiplier before spike)
DEMAND_SPIKES = {
    "MED-006": (10, 0.40),   # ORS: monsoon diarrhoea cases
    "MED-004": (8, 0.62),    # Salbutamol: air-quality / seasonal asthma
    "MED-008": (12, 0.75),   # Pantoprazole: new prescriber pattern
}
