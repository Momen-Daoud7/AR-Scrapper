VALID_ENGINES = [
    "CFM56-3B1", "CFM56-3B2", "CFM56-3C1", "CFM56-5A1", "CFM56-5A3",
    "CFM56-5B1", "CFM56-5B3", "CFM56-5B4", "CFM56-5B5", "CFM56-5B6",
    "CFM56-5B7", "CFM56-7B20", "CFM56-7B22", "CFM56-7B24", "CFM56-7B26",
    "CFM56-7B27", "RB211-535E4", "PW2037", "PW2040", "CF6-50",
    "CF6-80A", "CF6-80C2", "CF6-80E1"
]

DESIRED_ENGINES = [
    # CFM56-7B Variations
    "CFM56-7B20", "CFM56-7B22", "CFM56-7B24", "CFM56-7B26", "CFM56-7B27",
    "CFM56-7B/20", "CFM56-7B/22", "CFM56-7B/24", "CFM56-7B/26", "CFM56-7B/27",
    "CFM567B",
    # CFM56-5B Variations
    "CFM56-5B1", "CFM56-5B2", "CFM56-5B3", "CFM56-5B4", "CFM56-5B5", "CFM56-5B6", "CFM56-5B7",
    "CFM56-5B/1", "CFM56-5B/2", "CFM56-5B/3", "CFM56-5B/4", "CFM56-5B/5", "CFM56-5B/6", "CFM56-5B/7",
    "CFM565B",
    # CF6-80C2B Variations
    "CF6-80C2B1", "CF6-80C2B2", "CF6-80C2B3", "CF6-80C2B4", "CF6-80C2B5", "CF6-80C2B6",
    "CF6-80C2B1F", "CF6-80C2B2F", "CF6-80C2B3F", "CF6-80C2B4F", "CF6-80C2B5F", "CF6-80C2B6F",
    "CF680C2B", "CF680C2"
]

CONDITION_PRIORITY = ["NS", "NE", "OH", "SV", "AR", "RP", "Mid-Life"]

# Email configuration
SENDER_EMAIL = "impoweredlab@gmail.com"
EMAIL_PASSWORD = "yicc hbck atdu dlkm"
RECIPIENT_EMAILS = [
    "momenfbi123@gmail.com",
    # Add other recipient emails here
]

# File paths
STORAGE_FILE = 'engine_data_storage.json'

# Timezone
TIMEZONE = 'Africa/Khartoum'