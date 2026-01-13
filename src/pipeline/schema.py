# src/pipeline/schema.py

SYNONYMS_META = {
    "battery_id": ["battery_id", "Battery", "battery", "cell_id"],
    "type": ["type", "step_type", "mode"],
    "start_time": ["start_time", "start", "time_start"],
    "ambient_temperature": ["ambient_temperature", "ambient temp", "ambient_temp", "ambient"],
    "test_id": ["test_id", "test"],
    "uid": ["uid", "unique_id"],
    "filename": ["filename", "file", "csv", "path"],
    "capacity": ["capacity", "Capacity", "cap", "discharge_capacity"],
    "Re": ["Re", "re", "resistance_electrolyte"],
    "Rct": ["Rct", "rct", "charge_transfer_resistance"],
}

SYNONYMS_TS = {
    "voltage_measured": ["Voltage_measured", "voltage_measured", "V_measured"],
    "current_measured": ["Current_measured", "current_measured", "I_measured"],
    "temperature_measured": ["Temperature_measured", "temperature_measured", "T_measured"],
    "current_load": ["Current_load", "current_load", "I_load"],
    "voltage_load": ["Voltage_load", "voltage_load", "V_load"],
    "time": ["Time", "time", "t"],
}
